from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sys
import time
from typing import Any, Dict, Iterator, Optional

import psutil
import requests

from ..common import PathIsh
from .common import tmp_popen, promnesia_bin, free_port


@dataclass
class Helper:
    host: str
    port: str
    process: psutil.Popen

    def get(self, path: str, *args):
        # check it's alive first so the error is cleaner
        assert self.process.poll() is None, self.process
        return requests.get(f'http://{self.host}:{self.port}' + path)

    def post(self, path: str, *, json: Optional[Dict[str, Any]] = None):
        assert self.process.poll() is None, self.process
        return requests.post(f'http://{self.host}:{self.port}' + path, json=json)


@contextmanager
def run_server(db: Optional[PathIsh] = None, *, timezone: Optional[str] = None) -> Iterator[Helper]:
    # TODO not sure, perhaps best to use a thread or something?
    # but for some tests makes more sense to test in a separate process
    with free_port() as pp:
        # ugh. under docker 'localhost' tries to bind it to ipv6 (::1) for some reason???
        host = '0.0.0.0' if Path('/.dockerenv').exists() else 'localhost'
        port = str(pp)
        args = [
            'serve',
            '--host', host,
            '--quiet',
            '--port', port,
            *([] if timezone is None else ['--timezone', timezone]),
            *([] if db is None else ['--db'  , str(db)]),
        ]
        with tmp_popen(promnesia_bin(*args)) as server_process:
            server = Helper(host=host, port=port, process=server_process)

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
