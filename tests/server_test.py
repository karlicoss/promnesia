from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
from shutil import copy
import signal
from subprocess import check_output, check_call, Popen, PIPE
import time
from typing import NamedTuple, ContextManager

import pytz

from integration_test import index_hypothesis


class Helper(NamedTuple):
    port: str

TEST_PORT = 16556 # TODO FIXME use proper random port
# search for Serving on :16556


def next_port():
    global TEST_PORT
    TEST_PORT += 1
    return TEST_PORT


@contextmanager
def tmp_popen(*args, **kwargs):
    with Popen(*args, **kwargs, preexec_fn=os.setsid) as p:
        try:
            yield p
        finally:
            # ugh. otherwise was getting orphaned children...
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)


@contextmanager
def wserver(config: Path): # TODO err not sure what type should it be... -> ContextManager[Helper]:
    port = str(next_port())
    path = (Path(__file__).parent.parent / 'run').absolute()
    cmd = [
        str(path), 'serve',
        '--quiet',
        '--port', port,
        '--config', str(config),
    ]
    with tmp_popen(cmd) as server:
        print("Giving few secs to start server up")
        time.sleep(3)
        print("Started server up")

        yield Helper(port=port)

        print("DONE!!!!")


@contextmanager
def _test_helper(tmp_path):
    tdir = Path(tmp_path)
    # TODO extract that into index_takeout?
    # TODO ugh. quite hacky...
    template_config = Path(__file__).parent.parent / 'testdata' / 'test_config.py'
    copy(template_config, tdir)
    config = tdir / 'test_config.py'
    with config.open('a') as fo:
        fo.write(f"OUTPUT_DIR = '{tdir}'")

    path = (Path(__file__).parent.parent / 'run').absolute()
    check_call([str(path), 'extract', '--config', config])

    with wserver(config=config) as srv:
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


def test_query_instapaper(tmp_path):
    tdir = Path(tmp_path)
    index_hypothesis(tdir)
    test_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    with wserver(config=tdir / 'test_config.py') as helper:
        response = post(f'http://localhost:{helper.port}/visits', f'url={test_url}')
        assert len(response) > 5
        # TODO actually test response?


def test_visits(tmp_path):
    test_url = 'https://takeout.google.com/settings/takeout'
    with _test_helper(tmp_path) as helper:
        for q in range(3):
            print(f"querying {q}")
            response = post(f'http://localhost:{helper.port}/visits', f'url={test_url}')
            assert len(response) == 1


def test_search(tmp_path):
    tdir = Path(tmp_path)
    index_hypothesis(tdir)
    test_url = "http://www.e-flux.com"
    with wserver(config=tdir / 'test_config.py') as helper:
        response = post(f'http://localhost:{helper.port}/search', f'url={test_url}')
        assert len(response) == 8


def test_visited(tmp_path):
    test_url = 'https://takeout.google.com/settings/takeout'
    with _test_helper(tmp_path) as helper:
        response = post(f'http://localhost:{helper.port}/visited', f"""urls:=["{test_url}","http://badurl.org"]""")
        assert response == [True, False]


def test_search_around(tmp_path):
    tdir = Path(tmp_path)
    index_hypothesis(tdir)
    test_ts = int(datetime.strptime("2017-05-22T10:58:14.082375+00:00", '%Y-%m-%dT%H:%M:%S.%f%z').timestamp())
    # test_ts = int(datetime(2016, 12, 13, 12, 31, 4, 229275, tzinfo=pytz.utc).timestamp())
    # TODO hmm. perhaps it makes more sense to run query in different process and server in main process for testing??
    with wserver(config=tdir / 'test_config.py') as helper:
        response = post(f'http://localhost:{helper.port}/search_around', f'timestamp={test_ts}')
        # TODO highlight original url in extension??
        assert 5 < len(response) < 20
