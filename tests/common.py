from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Iterator, TypeVar

import pytest
import requests

from promnesia.tests.common import free_port


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
def local_http_server(path: Path) -> Iterator[str]:
    address = '127.0.0.1'
    with (
        free_port() as port,
        tmp_popen([sys.executable, '-m', 'http.server', '--directory', path, '--bind', address, str(port)]) as popen,
    ):
        endpoint = f'http://{address}:{port}'

        # meh.. but not sure if there is a better way to find out whether it's ready to serve requests
        for _attempt in range(50):
            try:
                requests.get(endpoint)
            except:
                time.sleep(0.05)
                continue
            else:
                break
        yield endpoint


T = TypeVar('T')


def notnone(x: T | None) -> T:
    assert x is not None
    return x
