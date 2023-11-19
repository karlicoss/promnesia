import gc
import os
from typing import NoReturn

import pytest


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
