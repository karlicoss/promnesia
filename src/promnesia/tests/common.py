from contextlib import closing, contextmanager
import gc
import inspect
import os
from pathlib import Path
import socket
import sys
from textwrap import dedent
from typing import Iterator, NoReturn, TypeVar

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


@contextmanager
def free_port() -> Iterator[int]:
    # this is a generator to make sure there are no race conditions between the time we call this and launch program
    #
    # also some relevant articles about this 'technique'
    # - https://eklitzke.org/binding-on-port-zero
    # - https://idea.popcount.org/2014-04-03-bind-before-connect
    # - https://blog.cloudflare.com/the-quantum-state-of-a-tcp-port
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        if sys.platform == 'linux':
            # Ok, so from what I've been reading, SO_REUSEADDR should only be necessary in the program that reuses the port
            # However, this answer (or man socket) claims we need it on both sites in Linux? see https://superuser.com/a/587955/300795
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # also not sure where REUSEADDR is set in uvicorn (e.g. here reuse_address isn't passed?)
        # https://github.com/encode/uvicorn/blob/6d666d99a285153bc4613e811543c39eca57054a/uvicorn/server.py#L162C37-L162C50
        # but from strace looks like it is called somewhere :shrug:

        # assign euphemeral port
        # see table in
        # https://stackoverflow.com/questions/14388706/how-do-so-reuseaddr-and-so-reuseport-differ/14388707#14388707
        # we rely on server binding to localhost later (or anything except 0.0.0.0 really)
        s.bind(('', 0))

        port = s.getsockname()[1]
        yield port
