from contextlib import contextmanager
from dataclasses import dataclass
import sys
import time
from typing import Any, Dict, Iterator, Optional

import requests

from ..common import PathIsh
from .common import tmp_popen, promnesia_bin


# TODO use proper random port
TEST_PORT = 16556


def next_port() -> int:
    global TEST_PORT
    TEST_PORT += 1
    return TEST_PORT


@dataclass
class Helper:
    port: str

    def get(self, path: str, *args):
        return requests.get(f'http://localhost:{self.port}' + path)

    def post(self, path: str, *, json: Optional[Dict[str, Any]] = None):
        return requests.post(f'http://localhost:{self.port}' + path, json=json)


@contextmanager
def run_server(db: Optional[PathIsh] = None, *, timezone: Optional[str] = None) -> Iterator[Helper]:
    port = str(next_port())
    cmd = [
        'serve',
        '--quiet',
        '--port', port,
        *([] if timezone is None else ['--timezone', timezone]),
        *([] if db is None else ['--db'  , str(db)]),
    ]
    # TODO not sure, perhaps best to use a thread or something?
    # but for some tests makes more sense to test in a separate process
    with tmp_popen(promnesia_bin(*cmd)) as server_process:
        server = Helper(port=port)

        # wait till ready
        for _ in range(50):
            try:
                server.get('/status').json()
                break
            except:
                time.sleep(0.1)
        else:
            raise RuntimeError("Cooldn't connect to '{st}' after 50 attempts")
        print("Started server up, db: {db}".format(db=db), file=sys.stderr)

        yield server

        # TODO use logger!
        print("Done with the server", file=sys.stderr)
