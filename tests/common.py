import os
import pytest # type: ignore

def skip_if_ci(reason):
    return pytest.mark.skipif('CI' in os.environ, reason=reason)
