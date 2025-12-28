import warnings

import pytest


@pytest.fixture(autouse=True)
def ignore_warnings():
    ## This is coming from HPI since we use tmp_config stuff
    # Hmm looking at it, the whole thing is pretty annoying...
    # I think maybe instead what should happen is
    # - if my.config is already present _and_ it's not the stub config, just use it
    # - only otherwise try messing with it
    warnings.filterwarnings("ignore", message="'my.config' package isn't found!")
    ##
    ## These are coming from hypothesis data access layer, doesn't matter for tests
    warnings.filterwarnings("ignore", message="You might want to 'pip install colorlog'")
    warnings.filterwarnings("ignore", message="recommended to 'pip install ijson'")
    warnings.filterwarnings("ignore", message="recommended to 'pip install orjson'")
    ##
