from pathlib import Path
from subprocess import check_call

from indexer_test import populate_db


testdata = Path(__file__).absolute().parent.parent / 'testdata'


# TODO need to generate config in the test??
class BaseConfig:
    pass


def index(cfg: Path):
    wd = Path(__file__).absolute().parent.parent
    check_call([
        'python3', '-m', 'wereyouhere',
        'extract',
        '--config', str(cfg),
    ], cwd=wd)


base_config = """
FALLBACK_TIMEZONE = 'Europe/Moscow'
EXTRACTORS = []
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
from cachew import DbBinder
from wereyouhere.common import DbVisit # TODO ugh. figure out pythonpath


def _get_stuff(outdir: Path):
    db_path = outdir / 'visits.sqlite'
    assert db_path.exists()

    engine = create_engine(f'sqlite:///{db_path}')

    # TODO ugh. 
    import sys
    print(sys.path)
    binder = DbBinder(DbVisit)

    meta = MetaData(engine)
    table = Table('visits', meta, *binder.db_columns)

    return engine, binder, table


def index_hypothesis(tdir: Path):
    cfg = tdir / 'test_config.py'
    cfg.write_text(base_config + f"""
OUTPUT_DIR = '{tdir}'

from wereyouhere.generator.smart import Wrapper as W
import wereyouhere.extractors.hypothesis as hypothesis

hyp_extractor = W(hypothesis.extract, '{testdata}/hypothesis/netrights-dashboards-mockup/data/annotations.json')

EXTRACTORS = [hyp_extractor]
    """)
    index(cfg)


def index_local_chrome(tdir: Path):
    # TODO mm, would be good to keep that for proper end2end
    # inp = Path('/L/data/wereyouhere/testdata/chrome-history/History') # TODO make it accessible to the repository
    # merged = tdir / 'chrome-merged.sqlite'
    # populate_db.merge_from('chrome', from_=inp, to=merged)

    merged = Path('/L/data/wereyouhere/testdata/chrome.sqlite')

    cfg = tdir / 'test_config.py'
    cfg.write_text(base_config + f"""
OUTPUT_DIR = '{tdir}'

from wereyouhere.generator.smart import Wrapper as W # TODO make it easier to use or get rid of whatsoever..
from wereyouhere.extractors.browser import chrome

chrome_extractor = W(chrome, '{merged}')

EXTRACTORS = [chrome_extractor]
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
