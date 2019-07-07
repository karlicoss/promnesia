from contextlib import contextmanager
import json
import os
from pathlib import Path
from shutil import copy
import signal
from subprocess import check_output, check_call, Popen, PIPE
import time
from typing import NamedTuple

from common import skip_if_ci

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
def _test_helper(tmp_path):
    tdir = Path(tmp_path)
    # TODO ugh. quite hacky...
    template_config = Path(__file__).parent.parent / 'testdata' / 'test_config.py'
    copy(template_config, tdir)
    config = tdir / 'test_config.py'
    with config.open('a') as fo:
        fo.write(f"OUTPUT_DIR = '{tdir}'")

    path = (Path(__file__).parent.parent / 'run').absolute()


    check_call([str(path), 'extract', '--config', config])

    port = str(next_port())
    cmd = [str(path), 'serve', '--port', port, '--config', config]
    with tmp_popen(cmd) as server:
        print("Giving few secs to start server up")
        time.sleep(3)
        print("Started server up")

        yield Helper(port=port)

        print("DONE!!!!")



@skip_if_ci("TODO dbcache")
def test_query(tmp_path):
    test_url = 'https://takeout.google.com/settings/takeout'
    with _test_helper(tmp_path) as helper:
        for q in range(3):
            print(f"querying {q}")
            cmd = [
                'http', 'post', f'http://localhost:{helper.port}/visits', f'url={test_url}',
            ]
            response = json.loads(check_output(cmd).decode('utf8'))
            assert len(response) > 0


@skip_if_ci("TODO dbcache")
def test_visited(tmp_path):
    test_url = 'https://takeout.google.com/settings/takeout'
    with _test_helper(tmp_path) as helper:
        cmd = [
            'http', 'post',  f'http://localhost:{helper.port}/visited', f"""urls:=["{test_url}","http://badurl.org"]""",
        ]
        response = json.loads(check_output(cmd))
        assert response == [True, False]
