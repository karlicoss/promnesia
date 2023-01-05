from promnesia.common import _is_windows

from common import tmp_popen, promnesia_bin

from pathlib import Path
import os
from subprocess import Popen
import time

import pytest


def ox_hugo_data() -> Path:
    p = Path('tests/testdata/ox-hugo/test/site')
    if not p.exists():
        raise RuntimeError(f"'{p}' not found! You propably need to run 'git submodule update --init --recursive'")
    assert p.exists(), p
    return p


def test_demo() -> None:
    if _is_windows:
        # for some reason fails to connect to server..
        # not sure maybe something with port choice idk
        pytest.skip("TODO broken on Windows")

    import requests
    with tmp_popen(promnesia_bin('demo', '--port', '16789', ox_hugo_data())):
        # FIXME why does it want post??
        time.sleep(2) # meh.. need a generic helper to wait till ready...
        res = {}
        for attempt in range(30):
            time.sleep(1)
            try:
                res = requests.post(
                    "http://localhost:16789/search",
                    json=dict(url="https://github.com/kaushalmodi/ox-hugo/issues"),
                ).json()
                break
            except:
                continue
        else:
            raise RuntimeError("Couldn't connect to the server")
        vis = res['visits']
        assert len(vis) > 50, vis
        mds  = [x for x in vis if x['locator']['title'] == 'content/posts/citations-example-toml.md'.replace('/', os.sep)]
        orgs = [x for x in vis if x['locator']['title'].startswith('content-org/single-posts/empty_tag.org'.replace('/', os.sep))]
        assert len(mds ) == 1
        assert len(orgs) == 1
