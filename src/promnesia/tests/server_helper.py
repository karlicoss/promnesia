from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil
import requests

from ..common import PathIsh
from .common import free_port, promnesia_bin, tmp_popen


@dataclass
class Helper:
    host: str
    port: str
    process: psutil.Popen

    def get(self, path: str):
        # check it's alive first so the error is cleaner
        assert self.process.poll() is None, self.process
        return requests.get(f'http://{self.host}:{self.port}' + path)

    def post(self, path: str, *, json: dict[str, Any] | None = None):
        assert self.process.poll() is None, self.process
        return requests.post(f'http://{self.host}:{self.port}' + path, json=json)


@contextmanager
def run_server(db: PathIsh | None = None, *, timezone: str | None = None) -> Iterator[Helper]:
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
            *([] if db is None else ['--db', str(db)]),
        ]  # fmt: skip
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
            print(f"Started server up, db: {db}", file=sys.stderr)

            yield server

            # TODO use logger!
            print("Done with the server", file=sys.stderr)
