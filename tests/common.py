import os
from functools import wraps
import pytest # type: ignore

def skip_if_ci(reason):
    return pytest.mark.skipif('CI' in os.environ, reason=reason)


def uses_x(f):
    @skip_if_ci('Uses X server')
    @wraps(f)
    def ff(*args, **kwargs):
        return f(*args, **kwargs)
    return ff
