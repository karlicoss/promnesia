import os
import time
from collections.abc import Iterator
from contextlib import ExitStack

import pytest


def parametrize_named(param: str, values):
    """
    by default pytest isn't showing param names in the test name which is annoying
    """
    return pytest.mark.parametrize(param, values, ids=[f'{param}={v}' for v in values])


def has_x() -> bool:
    return 'DISPLAY' in os.environ


@pytest.fixture
def exit_stack() -> Iterator[ExitStack]:
    """
    Useful to request ExitStack in a test to avoid excessive indentation.
    """
    with ExitStack() as stack:
        yield stack


def timeout(seconds: float) -> Iterator[None]:
    before = time.monotonic()
    while time.monotonic() - before < seconds:
        yield
    raise TimeoutError(f'Timeout after {seconds=}')
