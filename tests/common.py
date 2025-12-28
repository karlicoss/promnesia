from __future__ import annotations

import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

import pytest
import requests
from loguru import logger  # noqa: F401  # used/impoted in other tests

from promnesia.tests.common import free_port, tmp_popen


def under_ci() -> bool:
    return 'CI' in os.environ


def skip_if_ci(reason):
    return pytest.mark.skipif(under_ci(), reason=reason)


# used in demos.py -- baybe get rid of it?
def uses_x(f):
    @skip_if_ci('Uses X server')
    @wraps(f)
    def ff(*args, **kwargs):
        return f(*args, **kwargs)

    return ff


@contextmanager
def local_http_server(path: Path) -> Iterator[str]:
    address = '127.0.0.1'
    with (
        free_port() as port,
        tmp_popen([sys.executable, '-m', 'http.server', '--directory', path, '--bind', address, str(port)]),
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


# TODO move to main package?
def notnone[T](x: T | None) -> T:
    assert x is not None
    return x
