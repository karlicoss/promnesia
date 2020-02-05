from pathlib import Path
from subprocess import check_call, run
from typing import Set, Dict, Optional

from indexer_test import populate_db
from common import tdir

import pytest


testdata = Path(__file__).absolute().parent.parent / 'testdata'


def index(cfg: Path):
    from promnesia.__main__ import do_index
    do_index(cfg)


base_config = """
INDEXERS = []
FILTERS = []
"""


def test_empty(tdir):
    cfg = tdir / 'test_config.py'
    cfg.write_text(base_config + f"""
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


def index_urls(urls: Dict[str, Optional[str]]):
    def idx(tdir: Path):
        cfg = tdir / 'test_config.py'
        cfg.write_text(base_config + f"""
OUTPUT_DIR = '{tdir}'

from promnesia.common import Indexer, PreVisit, Loc
from datetime import datetime, timedelta
indexer = Indexer(
    lambda: [PreVisit(
        url=url,
        dt=datetime.min + timedelta(days=5000),
        locator=Loc.make('adhoc'),
        context=ctx,
    ) for url, ctx in {urls}.items()],
    src='adhoc',
)

INDEXERS = [indexer]
""")
        index(cfg)
    return idx


def index_hypothesis(tdir: Path):
    # TODO meh..
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
    cfg.write_text(base_config + f"""
OUTPUT_DIR = '{tdir}'

from promnesia.common import Indexer as I

def hyp_extractor():
    class hypothesis:
        export_path = '{testdata}/hypothesis/netrights-dashboards-mockup/data/annotations.json'

    import my
    mycfg = my.mycfg
    mycfg.paths.hypothesis = hypothesis

    from promnesia.kython.kimport import import_from
    he = import_from('{hypexport_path.parent}', 'hypexport')
    base = 'mycfg.repos'
    import importlib
    importlib.import_module(base)  # need to warm up, otherwise later import of 'mycfg.repos.<repo>' fails
    # TODO could warm up in mypkg as well?
    import sys
    sys.modules[base + '.hypexport'] = he

    import promnesia.indexers.hypothesis as hypi
    return I(
        hypi.index,
        src='hyp',
    )

# in addition, test for lazy indexers. useful for importing packages
INDEXERS = [hyp_extractor]
    """)
    index(cfg)


def index_local_chrome(tdir: Path):
    # TODO mm, would be good to keep that for proper end2end
    # inp = Path('/L/data/promnesia/testdata/chrome-history/History') # TODO make it accessible to the repository
    # merged = tdir / 'chrome-merged.sqlite'
    # populate_db.merge_from('chrome', from_=inp, to=merged)

    merged = Path('/L/data/promnesia/testdata/chrome.sqlite')

    cfg = tdir / 'test_config.py'
    cfg.write_text(base_config + f"""
OUTPUT_DIR = '{tdir}'

from promnesia.common import Indexer as I
from promnesia.indexers.browser import chrome

chrome_extractor = I(chrome, '{merged}', src='chrome')

INDEXERS = [chrome_extractor]
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

