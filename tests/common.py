from functools import wraps
import os
from pathlib import Path
import sys
import time
from typing import Iterator, Optional, TypeVar

import pytest
import requests


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
    import psutil
    with psutil.Popen(*args, **kwargs) as p:
        try:
            yield p
        finally:
            for c in p.children(recursive=True):
                c.kill()
            p.kill()
            p.wait()


@contextmanager
def local_http_server(path: Path, *, port: int) -> Iterator[str]:
    address = '127.0.0.1'
    with tmp_popen([sys.executable, '-m', 'http.server', '--directory', path, '--bind', address, str(port)]) as popen:
        endpoint = f'http://{address}:{port}'

        # meh.. but not sure if there is a better way to find out whether it's ready to serve requests
        for attempt in range(50):
            try:
                requests.get(endpoint)
            except:
                time.sleep(0.05)
                continue
            else:
                break
        yield endpoint


T = TypeVar('T')

def notnone(x: Optional[T]) -> T:
    assert x is not None
    return x
