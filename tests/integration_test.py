from pathlib import Path
from subprocess import check_call

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


def test_hypothesis(tmp_path):
    tdir = Path(tmp_path)
    cfg = tdir / 'test_config.py'
    cfg.write_text(base_config + f"""
OUTPUT_DIR = '{tdir}'

from wereyouhere.generator.smart import Wrapper as W
import wereyouhere.extractors.hypothesis as hypothesis

hyp_extractor = W(hypothesis.extract, '{testdata}/hypothesis/netrights-dashboards-mockup/_data/annotations.json')

EXTRACTORS = [hyp_extractor]
    """)
    index(cfg)
