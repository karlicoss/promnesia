from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from shutil import copy
import signal
import sys
from subprocess import check_output, check_call, PIPE
from textwrap import dedent
import time
from typing import NamedTuple, ContextManager, Optional

import pytz
import requests

from promnesia.common import PathIsh, _is_windows

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
        sys.executable, '-m', 'httpie',
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


def test_visits(tmp_path: Path) -> None:
    test_url = 'https://takeout.google.com/settings/takeout'
    with _test_helper(tmp_path) as helper:
        # TODO why are we querying 3 times ???
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


def test_visited(tmp_path: Path) -> None:
    test_url = 'https://takeout.google.com/settings/takeout'
    with _test_helper(tmp_path) as helper:
        endp = f'http://localhost:{helper.port}/visited'
        res = post(endp, f'''urls:=["{test_url}","http://badurl.org"]''')
        [r1, r2] = res
        assert r1 is not None
        assert r2 is None
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
    dt_extra = pytz.timezone('America/New_York').localize(datetime.fromisoformat('2018-06-01T10:00:00.000000'))
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


def test_status_ok(tmp_path: Path) -> None:
    dt_extra = pytz.timezone('Europe/London').localize(datetime.fromisoformat('2018-06-01T10:00:00.000000'))
    index_some_demo_visits(tmp_path, count=10, base_dt=dt_extra, delta=timedelta(hours=1), update=False)

    db_path = tmp_path / 'promnesia.sqlite'
    with wserver(db=db_path) as helper:
        response = post(f'http://localhost:{helper.port}/status')

        version = response['version']
        assert version is not None
        assert len(version.split('.')) >= 2  # random check..

        assert response['db'] == str(db_path)

        assert response['stats'] == {'total_visits': 10}


def test_status_error(tmp_path: Path) -> None:
    with wserver(db='/does/not/exist') as helper:
        response = post(f'http://localhost:{helper.port}/status')

        version = response['version']
        assert version is not None
        assert len(version.split('.')) >= 2 # random check..

        assert 'ERROR' in response['db'] # defensive, it doesn't exist


def test_basic(tmp_path: Path) -> None:
    cfg = tmp_path / 'config.py'
    cfg.write_text("SOURCES = ['promnesia.sources.demo']")
    check_call(promnesia_bin('index', '--config', cfg))
    with wserver() as helper:
        response = post(f'http://localhost:{helper.port}/visits', 'url=whatever')
        assert response['visits'] == []


def test_query_while_indexing(tmp_path: Path) -> None:
    cfg = tmp_path / 'config.py'
    indexing_cmd = promnesia_bin('index', '--config', cfg)

    # just trigger the database
    cfg.write_text(dedent(f'''
    OUTPUT_DIR = r'{tmp_path}'
    SOURCES = ['promnesia.sources.demo']
    '''))
    check_call(indexing_cmd)

    cfg.write_text(dedent(f'''
    OUTPUT_DIR = r'{tmp_path}'

    from promnesia.common import Source
    from promnesia.sources import demo
    # index stupid amount of visits to increase time spent in database serialization
    SOURCES = [Source(demo.index, count=100000)]
    '''))
    with wserver(db=tmp_path / 'promnesia.sqlite') as helper:
        status = lambda: post(f'http://localhost:{helper.port}/status')
        # precondition -- db should be healthy
        r = status()
        assert 0 < r['stats']['total_visits'] < 100000, r

        # now run the indexing (asynchronously)
        #
        from subprocess import Popen
        with Popen(indexing_cmd):
            # and hammer the backend to increase likelihood of race condition
            # not ideal -- doesn't really 'guarantee' to catch races, but good enough
            for _ in range(100):
                r = status()
                assert r['stats'].get('total_visits', 0) > 0, r
        # after indexing finished, new visits should be in the db
        r = status()
        assert r['stats']['total_visits'] >= 100000, r
