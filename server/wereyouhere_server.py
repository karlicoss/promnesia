#!/usr/bin/python3
import argparse
import json
import re
import os
import sys
from datetime import timedelta, datetime
from pathlib import Path

import hug # type: ignore
import hug.types as T # type: ignore


def log(*things):
    # TODO proper logging
    print(*things, file=sys.stderr, flush=True)


# TODO how to have a worker in parallel??

DELTA = timedelta(minutes=20)

LINKSDB = 'WEREYOUHERE_LINKSDB'

class State:
    def __init__(self, links: Path) -> None:
        self.links = links

        self.vmap = None
        self.last = None

    def refresh(self):
        now = datetime.now()
        if self.last is not None and (now - self.last) < DELTA:
            return

        # TODO use that?? https://github.com/timothycrosley/hug/blob/develop/tests/test_async.py
        log("Reloading the map")
        with self.links.open('r') as fo:
            self.vmap = json.load(fo)
        self.last = now

    def get_map(self):
        self.refresh()
        return self.vmap
        # TODO how to do it in background??

    # TODO could even store in some decent format now instead of lists...
    # res = {}
    # for u, (vis, cont) in vmap.items():
    #     res[u] = {
    #         'visits': vis,
    #         'contexts': cont,
    #     }
    # return res

state = None
def get_state():
    global state
    if state is None:
        state = State(Path(os.environ.get(LINKSDB)))
    return state


from normalise import normalise_url
# TODO hacky!

@hug.local()
@hug.post('/visits')
def visits(
        url: T.text,
):
    url = normalise_url(url)
    vmap = get_state().get_map()
    res = vmap.get(url, None)
    log(res)
    return res

@hug.local()
@hug.post('/visited')
def visited(
        urls, # TODO type
):
    vmap = get_state().get_map()
    nurls = list(map(normalise_url, urls))
    log(nurls)
    return [
        u in vmap for u in nurls
    ]


def run(port: str, linksdb: str):
    env = os.environ.copy()
    # # not sure if there is a simpler way to communicate with the server...
    env[LINKSDB] = linksdb
    os.execvpe(
        '/home/karlicos/.local/bin/hug',
        [
            'wereyouhere-server',
            '-p', port,
            '-f', __file__,
        ],
        env,
    )

def setup_parser(p):
    p.add_argument('--port', type=str, default='13131', help='Port for communicating with extension')
    p.add_argument('--links', type=str, default='/L/data/wereyouhere/linksdb.json', help='Path to links database')

def main():
    p = argparse.ArgumentParser('wereyouhere server', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    setup_parser(p)
    args = p.parse_args()
    run(args.port, args.links)

if __name__ == '__main__':
    main()
