from contextlib import contextmanager
import gc
import inspect
import os
from pathlib import Path
import sys
from textwrap import dedent
from typing import NoReturn, TypeVar

import pytest

from ..common import _is_windows, Res


def under_ci() -> bool:
    return 'CI' in os.environ


def throw(x: Exception) -> NoReturn:
    '''
    like raise, but can be an expression...
    '''
    raise x


@pytest.fixture
def gc_control(gc_on: bool):
    if gc_on:
        # no need to do anything, should be on by default
        yield
        return

    gc.disable()
    try:
        yield
    finally:
        gc.enable()


running_on_ci = 'CI' in os.environ


GIT_ROOT = Path(__file__).absolute().parent.parent.parent.parent
TESTDATA = GIT_ROOT / 'tests/testdata'


def get_testdata(path: str) -> Path:
    assert TESTDATA.is_dir()
    res = TESTDATA / path
    if not res.exists():
        raise RuntimeError(f"'{res}' not found! You propably need to run 'git submodule update --init --recursive'")
    return TESTDATA / path


@contextmanager
def tmp_popen(*args, **kwargs):
    import psutil
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
    # ugh. on windows there is no bash so can't use the script
    # whatever...
    if under_ci() or _is_windows:
        # should be able to use the installed version
        return [sys.executable, '-m', 'promnesia', *args]
    else:
        # use version from the repository
        root = Path(__file__).parent.parent.parent.parent
        pm = root / 'scripts/promnesia'
        return [pm, *args]


# meh... not great
@pytest.fixture
def reset_filters():
    from .. import extract

    extract.filters.cache_clear()
    try:
        yield
    finally:
        extract.filters.cache_clear()


# TODO could be a TypeGuard from 3.10
V = TypeVar('V')

def unwrap(r: Res[V]) -> V:
    assert not isinstance(r, Exception), r
    return r


def write_config(path: Path, gen, **kwargs) -> None:
    output_dir = path.parent
    cfg_src = dedent('\n'.join(inspect.getsource(gen).splitlines()[1:])) + f"\nOUTPUT_DIR = r'{output_dir}'"
    for k, v in kwargs.items():
        assert k in cfg_src, k
        cfg_src = cfg_src.replace(k, repr(str(v)))  # meh
    path.write_text(cfg_src)
