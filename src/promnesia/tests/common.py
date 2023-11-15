import gc
import os

import pytest


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
