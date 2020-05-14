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


GIT_ROOT = Path(__file__).parent.parent.absolute()
DATA = GIT_ROOT / 'tests/testdata'


# todo deprecate?
def tdata(path: str) -> str:
    assert DATA.is_dir(), DATA
    return str(DATA / path)
