import os
import time

from ..common import _is_windows

from .common import get_testdata, promnesia_bin, tmp_popen

import pytest
import requests


ox_hugo_data = get_testdata('ox-hugo/test/site')


def test_demo() -> None:
    if _is_windows:
        # for some reason fails to connect to server..
        # not sure maybe something with port choice idk
        pytest.skip("TODO broken on Windows")

    with tmp_popen(promnesia_bin('demo', '--port', '16789', ox_hugo_data)):
        # TODO why does it want post??
        time.sleep(2)  # meh.. need a generic helper to wait till ready...
        res = {}
        for _attempt in range(30):
            time.sleep(1)
            try:
                res = requests.post(
                    "http://localhost:16789/search",
                    json={'url': "https://github.com/kaushalmodi/ox-hugo/issues"},
                ).json()
                break
            except:
                continue
        else:
            raise RuntimeError("Couldn't connect to the server")
        vis = res['visits']
        assert len(vis) > 50, vis
        mds = [x for x in vis if x['locator']['title'] == 'content/posts/citations-example-toml.md'.replace('/', os.sep)]
        orgs = [x for x in vis if x['locator']['title'].startswith('content-org/single-posts/empty_tag.org'.replace('/', os.sep))]
        assert len(mds) == 1
        assert len(orgs) == 1
