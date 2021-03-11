from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from shutil import copy
import signal
import sys
from subprocess import check_output, check_call, PIPE
import time
from typing import NamedTuple, ContextManager, Optional

import pytz
import requests

from promnesia.common import PathIsh
from promnesia.py37 import fromisoformat

from integration_test import index_hypothesis, index_urls, index_some_demo_visits
from common import tdir, under_ci, tdata, tmp_popen, promnesia_bin


class Helper(NamedTuple):
    port: str


# TODO use proper random port
TEST_PORT = 16556


def next_port():
    global TEST_PORT
    TEST_PORT += 1
    return TEST_PORT


@contextmanager
def wserver(db: Optional[PathIsh]=None): # TODO err not sure what type should it be... -> ContextManager[Helper]:
    port = str(next_port())
    cmd = [
        'serve',
        '--quiet',
        '--port', port,
        *([] if db is None else ['--db'  , str(db)]),
    ]
    with tmp_popen(promnesia_bin(*cmd)) as server:
        # wait till ready
        st = f'http://localhost:{port}/status'
        for a in range(50):
            try:
                requests.get(st).json()
                break
            except:
                time.sleep(0.1)
        else:
            raise RuntimeError("Cooldn't connect to '{st}' after 50 attempts")
        print("Started server up, db: {db}".format(db=db), file=sys.stderr)

        yield Helper(port=port)

        print("Done with the server", file=sys.stderr)


@contextmanager
def _test_helper(tmp_path):
    tdir = Path(tmp_path)
    cache_dir = tdir / 'cache'
    cache_dir.mkdir()

    # TODO extract that into index_takeout?
    # TODO ugh. quite hacky...
    template_config = tdata('test_config.py')
    copy(template_config, tdir)
    config = tdir / 'test_config.py'
    with config.open('a') as fo:
        fo.write(f"""
OUTPUT_DIR = r'{tdir}'
CACHE_DIR  = r'{cache_dir}'
""")

    check_call(promnesia_bin('index', '--config', config))

    with wserver(db=tdir / 'promnesia.sqlite') as srv:
        yield srv


def post(*args):
    cmd = [
        'http',
        # '--timeout', '10000', # useful for debugging
        '--ignore-stdin',
        'post',
        *args,
    ]
    return json.loads(check_output(cmd).decode('utf8'))


def test_query_instapaper(tdir):
    index_hypothesis(tdir)
    test_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    with wserver(db=tdir / 'promnesia.sqlite') as helper:
        response = post(f'http://localhost:{helper.port}/visits', f'url={test_url}')
        assert len(response['visits']) > 5
        # TODO actually test response?


def test_visits(tmp_path):
    test_url = 'https://takeout.google.com/settings/takeout'
    with _test_helper(tmp_path) as helper:
        for q in range(3):
            print(f"querying {q}")
            response = post(f'http://localhost:{helper.port}/visits', f'url={test_url}')
            assert len(response['visits']) == 1


def test_search(tdir):
    index_hypothesis(tdir)
    test_url = "http://www.e-flux.com"
    with wserver(db=tdir / 'promnesia.sqlite') as helper:
        response = post(f'http://localhost:{helper.port}/search', f'url={test_url}')
        assert len(response['visits']) == 8


def test_visited(tmp_path):
    test_url = 'https://takeout.google.com/settings/takeout'
    with _test_helper(tmp_path) as helper:
        endp = f'http://localhost:{helper.port}/visited'
        assert post(endp, f'''urls:=["{test_url}","http://badurl.org"]''') == [True, False]
        assert post(endp, f'''urls:=[]''') == []


import pytest
@pytest.mark.parametrize('count',
    [1, 5, 10, 12, 25, 50, 100, 200, 400, 800, 1600]
)
def test_visited_benchmark(count: int, tmp_path) -> None:
    pytest.skip("Only works on @karlicoss computer for now")
    # TODO skip on ci
    import promnesia.server as S
    # TODO reset after?
    S.EnvConfig.set(S.ServerConfig(
        # TODO populate with test db and benchmark properly...
        db=Path('/todo'),
        timezone=pytz.utc,
    ))
    links = [f'https://reddit.com/whatever{i}.html' for i in range(count)]
    res = S.visited(links)
    assert len(res) == len(links)


def test_search_around(tmp_path: Path) -> None:
    # EDT, should be UTC-4
    dt_extra = pytz.timezone('America/New_York').localize(fromisoformat('2018-06-01T10:00:00.000000'))
    # NOTE: negative timedelta to test that it captures some past context
    # at the moment it's hardcoded by delta_back/delta_front -- would be nice to make it configurable later...
    index_some_demo_visits(tmp_path, count=1000, base_dt=dt_extra, delta=-timedelta(minutes=1), update=False)

    # TODO hmm. perhaps it makes more sense to run query in different process and server in main process for testing??
    with wserver(db=tmp_path / 'promnesia.sqlite') as helper:
        response = post(f'http://localhost:{helper.port}/search_around', f'timestamp={int(dt_extra.timestamp())}')
        assert len(response['visits']) > 10, response


# TODO right.. I guess that triggered because of reddit indexer specifically
# TODO could probably reuse parts of tests to be both integration/server and end2end when necessary?
def test_visits_hier(tdir):
    test_url = 'https://www.reddit.com/r/QuantifiedSelf/comments/d6m7bd/android_app_to_track_and_export_application_use/'
    urls = {
        test_url: 'parent url',
        'https://reddit.com/r/QuantifiedSelf/comments/d6m7bd/android_app_to_track_and_export_application_use/f0vem56': 'Some context',
        'https://reddit.com/r/QuantifiedSelf/comments/d6m7bd/android_app_to_track_and_export_application_use/whatever': None, # no context so should be ignored..
    }
    indexer = index_urls(urls)
    indexer(tdir)
    with wserver(db=tdir / 'promnesia.sqlite') as helper:
        response = post(f'http://localhost:{helper.port}/visits', f'url={test_url}')
        assert {v['context'] for v in response['visits']} == {'parent url', 'Some context'}


def test_status(tdir):
    with wserver(db='/does/not/exist') as helper:
        response = post(f'http://localhost:{helper.port}/status')
        assert 'ERROR' in response['db'] # defensive, it doesn't exist
        version = response['version']
        assert version is not None
        assert len(version.split('.')) >= 2 # random check..


# test default path (user data dir)
def test_basic(tmp_path: Path):
    cfg = tmp_path / 'config.py' # TODO put in user home dir? annoying in test...
    cfg.write_text('''
SOURCES = ['promnesia.sources.demo']
''')
    check_call(promnesia_bin('index', '--config', cfg))
    with wserver() as helper:
        response = post(f'http://localhost:{helper.port}/visits', 'url=whatever')
        assert response['visits'] == []
