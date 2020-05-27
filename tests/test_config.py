import pytest # type: ignore

from promnesia import Source


def test_minimal():
    '''
    Example of a smallest possible config, using a 'demo' source
    '''
    cfg = make('''
from promnesia import Source
from promnesia.sources import demo

SOURCES = [
    Source(demo.index),
]
''')
    assert len(cfg.sources) == 1
    assert all(isinstance(s, Source) for s in cfg.sources)
    # todo output dirs?


def test_no_sources():
    cfg = make('''
''')
    # raises because no SOURCES
    with pytest.raises(RuntimeError):
        cfg.sources


def test_empty_sources():
    cfg = make('''
SOURCES = []
    ''')
    # raises because empty SOURCES
    with pytest.raises(RuntimeError):
        cfg.sources


from pathlib import Path
from tempfile import TemporaryDirectory

from promnesia.config import import_config, Config


def make(body: str) -> Config:
    with TemporaryDirectory() as td:
        tdir = Path(td)
        cp = tdir / 'cfg.py'
        cp.write_text(body)
        return import_config(cp)
