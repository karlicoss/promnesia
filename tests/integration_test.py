from datetime import datetime, timedelta
import os
from pathlib import Path
from subprocess import check_call, run, Popen
from textwrap import dedent
from typing import Set, Dict, Optional, Union, Sequence, Tuple, Mapping, List

from promnesia.py37 import fromisoformat

import pytest

from common import tdir, under_ci, DATA, GIT_ROOT, promnesia_bin


def run_index(cfg: Path, *, update=False) -> None:
    from promnesia.__main__ import do_index
    do_index(cfg, overwrite_db=not update)


index = run_index # legacy name


def test_example_config(tdir) -> None:
    from promnesia.__main__ import read_example_config
    ex = read_example_config()
    cfg = tdir / 'test_config.py'
    cfg.write_text(ex)
    index(cfg)


from sqlalchemy import create_engine, MetaData, exists # type: ignore
from sqlalchemy import Column, Table # type: ignore
from cachew import NTBinder
from promnesia.common import DbVisit # TODO ugh. figure out pythonpath


# todo reuse promnesia.server??
def _get_stuff(outdir: Path):
    db_path = outdir / 'promnesia.sqlite'
    assert db_path.exists()

    engine = create_engine(f'sqlite:///{db_path}')

    binder = NTBinder.make(DbVisit)

    meta = MetaData(engine)
    table = Table('visits', meta, *binder.columns)

    return engine, binder, table

# TODO a bit shit... why did I make it dict at first??
Urls = Union[
           Mapping[str, Optional[str]],
    Sequence[Tuple[str, Optional[str]]],
]

def index_urls(urls: Urls):
    uuu = list(urls.items()) if isinstance(urls, dict) else urls

    def idx(tdir: Path):
        cfg = tdir / 'test_config.py'
        cfg.write_text(f"""
OUTPUT_DIR = r'{tdir}'

from promnesia.common import Source, Visit, Loc
from datetime import datetime, timedelta
# todo reuse demo indexer?
indexer = Source(
    lambda: [Visit(
        url=url,
        dt=datetime.min + timedelta(days=5000) + timedelta(hours=i),
        locator=Loc.make('test'),
        context=ctx,
    ) for i, (url, ctx) in enumerate({uuu})],
    name='test',
)

SOURCES = [indexer]
""")
        index(cfg)
    return idx


def index_hypothesis(tdir: Path) -> None:
    hypexport_path  = DATA / 'hypexport'
    hypothesis_data = hypexport_path / 'testdata'

    cfg = tdir / 'test_config.py'
    # TODO ok, need to simplify this...
    cfg.write_text(f"""
OUTPUT_DIR = r'{tdir}'

from promnesia.common import Source

def hyp_extractor():
    import my.config
    class user_config:
        export_path = r'{str(hypothesis_data)}/netrights-dashboard-mockup/data/*.json'
    my.config.hypothesis = user_config

    # todo ideally would use virtualenv?
    import sys
    sys.path.insert(0, r"{str(hypexport_path / 'src')}")

    import promnesia.sources.hypothesis as hypothesis
    yield from hypothesis.index()

# in addition, test for lazy indexers. useful for importing packages
SOURCES = [
    Source(hyp_extractor, name='hyp'),
]
    """)
    index(cfg)


def index_some_demo_visits(
    tmp_path: Path,
    *,
    count: int,
    base_dt: datetime,
    delta: timedelta,
    update: bool,
) -> None:
    cfg = dedent(f'''
    OUTPUT_DIR = r'{tmp_path}'

    # todo would be nice if it was possible without importing anything at all
    def make_visits():
        from datetime import timedelta
        from promnesia.sources import demo
        from promnesia.py37 import fromisoformat

        # todo hmm, a bit messy, would be nice to do it in a more straighforward manner..
        yield from demo.index(
            count={count},
            base_dt=fromisoformat('{base_dt.isoformat()}'),
            delta=timedelta(seconds={delta.total_seconds()}),
        )

    from promnesia.common import Source
    SOURCES = [
        Source(make_visits, name='demo'),
    ]
    ''')
    cfg_file = tmp_path / 'test_config_extra.py'
    cfg_file.write_text(cfg)
    run_index(cfg_file, update=update)


def index_local_chrome(tdir: Path):
    # TODO mm, would be good to keep that for proper end2end
    # inp = Path('/L/data/promnesia/testdata/chrome-history/History') # TODO make it accessible to the repository
    # merged = tdir / 'chrome-merged.sqlite'
    # populate_db.merge_from('chrome', from_=inp, to=merged)

    merged = Path('/L/data/promnesia/testdata/chrome.sqlite')

    cfg = tdir / 'test_config.py'
    cfg.write_text(f"""
OUTPUT_DIR = r'{tdir}'

from promnesia.common import Indexer as I
# TODO FIXME -- fix back
from promnesia.sources.browser import chrome

chrome_extractor = I(chrome, '{merged}', src='chrome')

SOURCES = [chrome_extractor]
""")
    index(cfg)


def query_db_visits(tdir: Path) -> List[DbVisit]:
    # TODO copy pasting from server; need to unify
    engine, binder, table = _get_stuff(tdir)
    query = table.select()
    with engine.connect() as conn:
        return [binder.from_row(row) for row in conn.execute(query)]


def test_hypothesis(tdir: Path) -> None:
    index_hypothesis(tdir)
    visits = query_db_visits(tdir)
    assert len(visits) > 100

    [vis] = [x for x in visits if 'fundamental fact of evolution' in (x.context or '')]

    assert vis.norm_url == 'wired.com/2017/04/the-myth-of-a-superhuman-ai'
    assert vis.orig_url == 'https://www.wired.com/2017/04/the-myth-of-a-superhuman-ai/'
    assert vis.locator.href == 'https://hyp.is/_Z9ccmVZEeexBOO7mToqdg/www.wired.com/2017/04/the-myth-of-a-superhuman-ai/'
    assert 'misconception about evolution is fueling misconception about AI' in (vis.context or '') # contains notes as well


def test_comparison(tdir: Path) -> None:
    from promnesia.compare import compare_files

    idx = index_urls({
        'https://example.com': None,
        'https://en.wikipedia.org/wiki/Saturn_V': None,
        'https://plato.stanford.edu/entries/qualia': None,
    })
    idx(tdir)
    db     = tdir / 'promnesia.sqlite'
    old_db = tdir / 'promnesia-old.sqlite'
    import shutil
    shutil.move(str(db), str(old_db))

    idx2 = index_urls({
        'https://example.com': None,
        'https://www.reddit.com/r/explainlikeimfive/comments/1ev6e0/eli5entropy': None,
        'https://en.wikipedia.org/wiki/Saturn_V': None,
        'https://plato.stanford.edu/entries/qualia': None,
    })
    idx2(tdir)

    # should not crash, as there are more links in the new database
    assert len(list(compare_files(old_db, db))) == 0

    assert len(list(compare_files(db, old_db))) == 1


def test_index_many(tdir: Path) -> None:
    # NOTE [20200521] experimenting with promnesia.dump._CHUNK_BY
    # inserting 100K visits
    # value=1000: 9 seconds
    # value=10  : 9 seconds
    # value=1   : 18 seconds
    # ok, I guess it's acceptable considering the alternative is crashing (too many sql variables on some systems)
    # kinda makes sense -- I guess most overhead is coming from creating temporary lists etc?
    cfg = tdir / 'test_config.py'
    cfg.write_text(f"""
from datetime import datetime, timedelta
from promnesia.common import Source, Visit, Loc
# TODO def need to allow taking in index function without having to wrap in source?
def index():
    for i in range(100000):
        yield Visit(
            url='http://whatever/page' + str(i),
            dt=datetime.min + timedelta(days=5000) + timedelta(hours=i),
            locator=Loc.make('test'),
        )

SOURCES = [Source(index)]
OUTPUT_DIR = r'{tdir}'
    """)
    index(cfg)
    visits = query_db_visits(tdir)

    assert len(visits) == 100000


def test_indexing_error(tdir: Path) -> None:
    cfg = tdir / 'test_config.py'
    cfg.write_text(f'''
def bad_index():
    import bad_import
    yield from [] # dummy
from promnesia.common import Source
from promnesia.sources import demo

SOURCES = [
    bad_index,
    Source(demo, count=3),
]
OUTPUT_DIR = r'{tdir}'
''')
    with pytest.raises(SystemExit):
        index(cfg)
        # should exit(1)

    # yet save the database
    visits = query_db_visits(tdir)

    [e, _, _, _] = visits
    assert e.src == 'error'


def test_indexing_update(tmp_path: Path) -> None:
    from collections import Counter

    index_hypothesis(tmp_path)
    visits = query_db_visits(tmp_path)
    counter = Counter(v.src for v in visits)
    assert counter['hyp'] > 50, counter  # precondition

    dt = fromisoformat('2018-06-01T10:00:00.000000+01:00')
    index_some_demo_visits(tmp_path, count=1000, base_dt=dt, delta=timedelta(hours=1), update=True)
    visits = query_db_visits(tmp_path)
    counter = Counter(v.src for v in visits)
    assert counter['demo'] == 1000, counter
    assert counter['hyp'] > 50, counter  # should keep the original visits too!


@pytest.mark.parametrize('execution_number', range(1))  # adjust this parameter to increase 'coverage
def test_concurrent_indexing(tmp_path: Path, execution_number) -> None:
    cfg_slow = tmp_path / 'config_slow.py'
    cfg_fast = tmp_path / 'config_fast.py'
    cfg = dedent(f'''
    OUTPUT_DIR = r'{tmp_path}'
    from promnesia.common import Source
    from promnesia.sources import demo
    SOURCES = [Source(demo.index, count=COUNT)]
    ''')
    cfg_slow.write_text(cfg.replace('COUNT', '100000'))
    cfg_fast.write_text(cfg.replace('COUNT', '100'   ))
    # init it first, to create the database
    # TODO ideally this shouldn't be necessary but it's reasonable that people would already have the index
    # otherwise it would fail at db creation point.. which is kinda annoying to work around
    # todo in principle can work around same way as in cachew, by having a loop around PRAGMA WAL command?
    check_call(promnesia_bin('index', '--config', cfg_fast))

    # run in the background
    with Popen(promnesia_bin('index', '--config', cfg_slow)) as slow:
        while slow.poll() is None:
            # create a bunch of 'smaller' indexers running in parallel
            fasts = [Popen(promnesia_bin('index', '--config', cfg_fast)) for _ in range(10)]
            for fast in fasts:
                assert fast.wait() == 0, fast  # should succeed
        assert slow.poll() == 0, slow
