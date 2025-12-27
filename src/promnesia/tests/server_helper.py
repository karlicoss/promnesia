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


@dataclass(kw_only=True)
class Backend:
    host: str
    port: str
    db: Path | None
    process: psutil.Popen

    def get(self, path: str):
        # check it's alive first so the error is cleaner
        assert self.process.poll() is None, self.process
        return requests.get(f'http://{self.host}:{self.port}' + path)

    def post(self, path: str, *, json: dict[str, Any] | None = None):
        assert self.process.poll() is None, self.process
        return requests.post(f'http://{self.host}:{self.port}' + path, json=json)

    @property
    def backend_dir(self) -> Path:
        # NOTE: only used in end2end tests -- not sure, maybe should do something idfferent
        assert self.db is not None
        return self.db.parent


@contextmanager
def run_server(db: PathIsh | None = None, *, timezone: str | None = None) -> Iterator[Backend]:
    # TODO not sure, perhaps best to use a thread or something?
    # but for some tests makes more sense to test in a separate process
    with free_port() as pp:
        # ugh. under docker 'localhost' tries to bind it to ipv6 (::1) for some reason???
        host = '0.0.0.0' if Path('/.dockerenv').exists() else 'localhost'
        port = str(pp)
        db_: Path | None = Path(db) if db is not None else None
        args = [
            'serve',
            '--host', host,
            '--quiet',
            '--port', port,
            *([] if timezone is None else ['--timezone', timezone]),
            *([] if db_ is None else ['--db', db_]),
        ]  # fmt: skip
        with tmp_popen(promnesia_bin(*args)) as server_process:
            server = Backend(host=host, port=port, db=db_, process=server_process)

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
