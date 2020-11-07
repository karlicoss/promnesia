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


from contextlib import contextmanager
@contextmanager
def tmp_popen(*args, **kwargs):
    import psutil # type: ignore
    with psutil.Popen(*args, **kwargs) as p:
        try:
            yield p
        finally:
            for c in p.children(recursive=True):
                c.kill()
            p.kill()
            p.wait()

# meh
def promnesia_bin(*args):
    # not sure it's a good idea to diverge, but not sure if there's a better way either?
    if under_ci():
        # should be able to use the installed version
        return ['promnesia', *args]
    else:
        # use version from the repository
        root = Path(__file__).parent.parent
        pm = root / 'scripts/promnesia'
        return [pm, *args]


from typing import Any, NoReturn
def throw(x: Any) -> NoReturn:
    '''
    like raise, but can be an expression...
    '''
    raise RuntimeError(x)
