import os
import sys
from functools import wraps
from pathlib import Path
from typing import Iterator, Optional, TypeVar

from promnesia.common import _is_windows

import pytest # type: ignore


def has_x() -> bool:
    # meh, not very portable, but good enough for now
    return 'DISPLAY' in os.environ


def under_ci() -> bool:
    return 'CI' in os.environ


def skip_if_ci(reason):
    return pytest.mark.skipif(under_ci(), reason=reason)


def uses_x(f):
    @skip_if_ci('Uses X server')
    @wraps(f)
    def ff(*args, **kwargs):
        return f(*args, **kwargs)
    return ff


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
    # ugh. on windows there is no bash so can't use the script
    # whatever...
    if under_ci() or _is_windows:
        # should be able to use the installed version
        return [sys.executable, '-m', 'promnesia', *args]
    else:
        # use version from the repository
        root = Path(__file__).parent.parent
        pm = root / 'scripts/promnesia'
        return [pm, *args]


@contextmanager
def local_http_server(path: Path, *, port: int) -> Iterator[str]:
    address = '127.0.0.1'
    with tmp_popen([sys.executable, '-m', 'http.server', '--directory', path, '--bind', address, str(port)]) as popen:
        yield f'http://{address}:{port}'


T = TypeVar('T')

def notnone(x: Optional[T]) -> T:
    assert x is not None
    return x
