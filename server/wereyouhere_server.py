#!/usr/bin/python3
import argparse
import json
import re
import os
import sys
from datetime import timedelta, datetime
from pathlib import Path
import functools
import logging

from kython import setup_logzero

import hug # type: ignore
import hug.types as T # type: ignore


_LINKSDB = 'WEREYOUHERE_LINKSDB'


# TODO kythonize?
from typing import NamedTuple
class PathWithMtime(NamedTuple):
    path: Path
    mtime: float

    @classmethod
    def make(cls, p: Path):
        return cls(
            path=p,
            mtime=p.stat().st_mtime,
        )


# meh. need this since I don't have hooks in hug to initialize logging properly..
logging_initialized = False
def get_logger():
    logger = logging.getLogger('wereyouhere')
    global logging_initialized
    if not logging_initialized:
        setup_logzero(logger, level=logging.DEBUG)
    return logger


# TODO how to have a worker in parallel??


class State:
    def __init__(self, links: Path) -> None:
        self.links_db = links

        logger = get_logger()
        logger.info("Reloading the map")

        # TODO use that?? https://github.com/timothycrosley/hug/blob/develop/tests/test_async.py
        with self.links_db.open('r') as fo:
            self.vmap = json.load(fo)

    def get_map(self):
        return self.vmap


@functools.lru_cache(1)
def _get_state(mpath: PathWithMtime):
    return State(mpath.path)

def get_state():
    path = Path(os.environ.get(_LINKSDB))
    return _get_state(PathWithMtime.make(path))


from normalise import normalise_url
# TODO hacky!

@hug.local()
@hug.post('/visits')
def visits(
        url: T.text,
):
    logger = get_logger()
    url = normalise_url(url)
    vmap = get_state().get_map()
    res = vmap.get(url, None)
    logger.debug(res)
    return res

@hug.local()
@hug.post('/visited')
def visited(
        urls, # TODO type
):
    logger = get_logger()
    vmap = get_state().get_map()
    nurls = list(map(normalise_url, urls))
    logger.debug(nurls)
    return [
        u in vmap for u in nurls
    ]


def run(port: str, linksdb: str):
    env = os.environ.copy()
    # # not sure if there is a simpler way to communicate with the server...
    env[_LINKSDB] = linksdb
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
    setup_logzero(get_logger(), level=logging.DEBUG)
    p = argparse.ArgumentParser('wereyouhere server', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    setup_parser(p)
    args = p.parse_args()
    run(args.port, args.links)

if __name__ == '__main__':
    main()
