from pathlib import Path
from subprocess import check_call
from typing import Set, Dict, Optional

from indexer_test import populate_db


testdata = Path(__file__).absolute().parent.parent / 'testdata'


def index(cfg: Path):
    from promnesia.__main__ import do_index
    do_index(cfg)


base_config = """
FALLBACK_TIMEZONE = 'Europe/Moscow'
INDEXERS = []
FILTERS = []
"""


def test_empty(tmp_path):
    tdir = Path(tmp_path)
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
    cfg = tdir / 'test_config.py'
    cfg.write_text(base_config + f"""
OUTPUT_DIR = '{tdir}'

from promnesia.common import Indexer as I
import promnesia.indexers.hypothesis as hypothesis

hyp_extractor = I(
    hypothesis.extract,
    '{testdata}/hypothesis/netrights-dashboards-mockup/data/annotations.json',
    src='hyp',
)

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


def test_hypothesis(tmp_path):
    tdir = Path(tmp_path)
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
