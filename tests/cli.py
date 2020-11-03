from common import tmp_popen

from pathlib import Path
from subprocess import Popen
import time


def ox_hugo_data() -> Path:
    p = Path('tests/testdata/ox-hugo/test/site')
    if not p.exists():
        raise RuntimeError(f"'{p}' not found! You propably need to run 'git submodules update --init'")
    assert p.exists(), p
    return p


def test_demo() -> None:
    import requests
    with tmp_popen(f'promnesia demo --port 16789 {ox_hugo_data()}'.split()):
        # FIXME why does it want post??
        time.sleep(2) # meh.. need a generic helper to wait till ready...
        res = {}
        for attempt in range(30):
            time.sleep(1)
            try:
                res = requests.post(
                    "http://localhost:16789/search",
                    data=dict(url="https://github.com/kaushalmodi/ox-hugo/issues")
                ).json()
                break
            except:
                continue
        else:
            raise RuntimeError("Couldn't connect to the server")
        vis = res['visits']
        assert len(vis) > 50, vis
        mds  = [x for x in vis if x['locator']['title'] == 'content/posts/citations-example-toml.md']
        orgs = [x for x in vis if x['locator']['title'] == 'content-org/single-posts/empty_tag.org' ]
        assert len(mds ) == 1
        assert len(orgs) == 1
