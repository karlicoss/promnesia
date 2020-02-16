import os
from functools import wraps
from pathlib import Path

import pytest # type: ignore


def under_ci():
    return 'CI' in os.environ


def skip_if_ci(reason):
    return pytest.mark.skipif(under_ci(), reason=reason)


def uses_x(f):
    @skip_if_ci('Uses X server')
    @wraps(f)
    def ff(*args, **kwargs):
        return f(*args, **kwargs)
    return ff


@pytest.fixture
def tdir(tmp_path):
    yield Path(tmp_path)


def tdata(path: str) -> Path:
    pp = Path(__file__).parent.parent / 'testdata'
    assert pp.is_dir()
    return pp.absolute() / path


