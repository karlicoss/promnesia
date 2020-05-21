from pathlib import Path
from subprocess import check_call, run
from typing import Set, Dict, Optional, Union, Sequence, Tuple

from indexer_test import populate_db
from common import tdir, under_ci, DATA, GIT_ROOT

import pytest

import platform
system = platform.system()


def index(cfg: Path):
    from promnesia.__main__ import do_index
    do_index(cfg)


def test_example_config(tdir):
    example = GIT_ROOT / 'config.py.example'
    ex = example.read_text()
    if under_ci():
        # TODO ugh fucking hell I couldn't find a single path that has HTMLs both on macos and ubuntu
        # and using /usr/share/docs locally might index a bit too much
        if system == 'Darwin':
            repl = '/usr/share/doc/cups/'
        else:
            repl = '/usr/share/doc/python3/'
        ex = ex.replace('/usr/share/doc/python3/html/faq', repl)
    cfg = tdir / 'test_config.py'
    cfg.write_text(ex)
    index(cfg)


# TODO not sure if makes a lot of sense? maybe on no indexers should actually error
def test_empty(tdir):
    cfg = tdir / 'test_config.py'
    cfg.write_text(f"""
SOURCES = []
OUTPUT_DIR = '{tdir}'
    """)
    index(cfg)


from sqlalchemy import create_engine, MetaData, exists # type: ignore
from sqlalchemy import Column, Table # type: ignore
from cachew import NTBinder
from promnesia.common import DbVisit # TODO ugh. figure out pythonpath


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
              Dict[str, Optional[str]],
    Sequence[Tuple[str, Optional[str]]],
]

def index_urls(urls: Urls):
    uuu = list(urls.items()) if isinstance(urls, dict) else urls

    def idx(tdir: Path):
        cfg = tdir / 'test_config.py'
        cfg.write_text(f"""
OUTPUT_DIR = '{tdir}'

from promnesia.common import Source, Visit, Loc
from datetime import datetime, timedelta
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


def index_hypothesis(tdir: Path):
    # TODO meh..
    # TODO use submodule?
    hypexport_path = Path(tdir) / 'hypexport'
    check_call([
        'git',
        'clone',
        # TODO do I need --recursive here?? I guess it's only for fetching new data?
        'https://github.com/karlicoss/hypexport',
        str(hypexport_path),
    ])

    cfg = tdir / 'test_config.py'
    # TODO ok, need to simplify this...
    cfg.write_text(f"""
OUTPUT_DIR = '{tdir}'

from promnesia.common import Source

def hyp_extractor():
    import my.config
    class user_config:
        export_path = '{str(DATA)}/hypothesis/netrights-dashboards-mockup/data/*.json'
        hypexport   = '{hypexport_path}'
    my.config.hypothesis = user_config

    import promnesia.sources.hypothesis as hypi
    return Source(
        hypi.index,
        src='hyp',
    )

# in addition, test for lazy indexers. useful for importing packages
SOURCES = [hyp_extractor]
    """)
    index(cfg)


def index_local_chrome(tdir: Path):
    # TODO mm, would be good to keep that for proper end2end
    # inp = Path('/L/data/promnesia/testdata/chrome-history/History') # TODO make it accessible to the repository
    # merged = tdir / 'chrome-merged.sqlite'
    # populate_db.merge_from('chrome', from_=inp, to=merged)

    merged = Path('/L/data/promnesia/testdata/chrome.sqlite')

    cfg = tdir / 'test_config.py'
    cfg.write_text(f"""
OUTPUT_DIR = '{tdir}'

from promnesia.common import Indexer as I
from promnesia.sources.browser import chrome

chrome_extractor = I(chrome, '{merged}', src='chrome')

SOURCES = [chrome_extractor]
""")
    index(cfg)


def test_hypothesis(tdir):
    index_hypothesis(tdir)

    # TODO copy pasting from server; need to unify
    engine, binder, table = _get_stuff(tdir)
    query = table.select()
    with engine.connect() as conn:
        visits = [binder.from_row(row) for row in conn.execute(query)]

    assert len(visits) > 100

    [vis] = [x for x in visits if 'fundamental fact of evolution' in x.context]

    assert vis.norm_url == 'wired.com/2017/04/the-myth-of-a-superhuman-ai'
    assert vis.orig_url == 'https://www.wired.com/2017/04/the-myth-of-a-superhuman-ai/'
    assert vis.locator.href == 'https://hyp.is/_Z9ccmVZEeexBOO7mToqdg/www.wired.com/2017/04/the-myth-of-a-superhuman-ai/'
    assert 'misconception about evolution is fueling misconception about AI' in vis.context # contains notes as well


def test_comparison(tdir: Path):
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
    shutil.move(db, old_db)

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


def test_index_many(tdir):
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
from promnesia import Source, Visit, Loc
# TODO def need to allow taking in index function without having to wrap in source?
def index():
    for i in range(100000):
        yield Visit(
            url='http://whatever/page' + str(i),
            dt=datetime.min + timedelta(days=5000) + timedelta(hours=i),
            locator=Loc.make('test'),
        )

SOURCES = [Source(index)]
OUTPUT_DIR = '{tdir}'
    """)
    index(cfg)
    #
    # TODO copy pasting from server; need to unify
    engine, binder, table = _get_stuff(tdir)
    query = table.select()
    with engine.connect() as conn:
        visits = [binder.from_row(row) for row in conn.execute(query)]

    assert len(visits) == 100000
