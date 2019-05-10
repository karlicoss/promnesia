#!/usr/bin/python3
__package__ = 'wereyouhere' # ugh. hacky way to make hug work properly...

import argparse
import json
import re
import os
import sys
from collections import OrderedDict
from datetime import timedelta, datetime
from pathlib import Path
import functools
import logging

from kython import setup_logzero

import hug # type: ignore
import hug.types as T # type: ignore


from .common import PathWithMtime, Config, Visit, Url, import_config, Loc
from .normalise import normalise_url
from .py37 import fromisoformat

_ENV_CONFIG = 'WEREYOUHERE_CONFIG'

# meh. need this since I don't have hooks in hug to initialize logging properly..
logging_initialized = False
def get_logger():
    logger = logging.getLogger('wereyouhere')
    global logging_initialized
    if not logging_initialized:
        setup_logzero(logger, level=logging.DEBUG)
    return logger


from typing import MutableMapping, Collection, List
VMap = MutableMapping[Url, List[Visit]]


def load_config() -> Config:
    cp = os.environ.get(_ENV_CONFIG)
    assert cp is not None
    return import_config(Path(cp))

# TODO how to have a worker in parallel??
# TODO check mode for verifying links etc

@functools.lru_cache(1)
def _get_state(mpath: PathWithMtime) -> VMap:
    logger = get_logger()
    logger.info("Reloading the map")
    # TODO use that?? https://github.com/timothycrosley/hug/blob/develop/tests/test_async.py
    config = load_config()

    links_db = mpath.path
    ints = json.loads(links_db.read_text())

    all_visits: VMap = OrderedDict()

    def reg_visit(v):
        url = v['url']
        vlist: List[Visit]
        if url not in all_visits:
            vlist = []
            all_visits[url] = vlist
        else:
            vlist = all_visits[url]
        # TODO parse loc
        for vis in v['visits']:
            dt = fromisoformat(vis['dt'])
            if dt.tzinfo is None:
                dt = config.FALLBACK_TIMEZONE.localize(dt)

            ld = vis['locator']
            loc = Loc(file=ld['file'], line=ld['line'])

            vlist.append(Visit(
                dt=dt,
                locator=loc,
                context=vis['context'],
                tag=vis['tag'],
            ))

    for src, src_visits in ints:
        for v in src_visits:
            reg_visit(v)

    for u, visits in all_visits.items():
        visits.sort(key=lambda v: v.cmp_key) # although shouldn't really matter; frontend has to sort them anyway

    return all_visits

def get_latest_db(cpath: Path) -> Path:
    config = load_config()
    idir = Path(config.OUTPUT_DIR) / 'intermediate'
    return max(idir.glob('*.json'))


def get_state(path: Path=None) -> VMap:
    if path is None:
        cp = os.environ.get(_ENV_CONFIG)
        assert cp is not None
        path = get_latest_db(Path(cp))
    return _get_state(PathWithMtime.make(path))


from typing import Dict

def as_json(v: Visit) -> Dict:
   #  "09 Aug 2018 19:48",
   #  "06 Aug 2018 21:36--21:37",
    # TODO perhaps tag merging should be done by browser as well?
    # TODO also local should be suppressed if any other tag with this timestamp is present
    dts = v.dt.strftime('%d %b %Y %H:%M')
    loc = v.locator
    locs = loc.file + (':' + str(loc.line) if loc.line is not None else '')
    return {
        # TODO do not display year if it's current year??
        'dt': dts,
        'tags': [v.tag],
        'context': v.context,
        'locator': locs,
    }


@hug.local()
@hug.post('/visits')
def visits(
        url: T.text,
):
    logger = get_logger()
    url = normalise_url(url)
    vmap = get_state()
    res = vmap.get(url, None)
    logger.debug(res)
    if res is None:
        return None
    else:
        return [as_json(v) for v in res]

@hug.local()
@hug.post('/visited')
def visited(
        urls, # TODO type
):
    logger = get_logger()
    vmap = get_state()
    nurls = list(map(normalise_url, urls))
    logger.debug(nurls)
    return [
        u in vmap for u in nurls
    ]


def run(port: str, config: Path):
    env = os.environ.copy()
    # # not sure if there is a simpler way to communicate with the server...
    env[_ENV_CONFIG] = str(config)
    os.execvpe(
        '/home/karlicos/.local/bin/hug',
        [
            'wereyouhere-server',
            '-p', port,
            '-f', __file__,
        ],
        env,
    )


_DEFAULT_CONFIG = Path('config.py')


def test_load():
    state = get_state(get_latest_db(Path('test_config.py')))
    from pprint import pprint
    pprint(state)

# TODO takes 22 secs for some reason... but works!
# I guess I need a smaller test db to run server against
def test_query():
    path = (Path(__file__).parent.parent / 'run_test').absolute()
    from subprocess import Popen, PIPE
    from subprocess import check_output
    import time
    import json
    PORT = "16555" # TODO random?
    cmd = [str(path), 'serve', '--port', PORT]
    print(cmd)
    with Popen(cmd, stdout=PIPE, stderr=PIPE) as server:
        time.sleep(5) # give it time to start up
        # TODO which url??
        test_url = 'https://slatestarcodex.com/2014/03/17/what-universal-human-experiences-are-you-missing-without-realizing-it/'
        response = json.loads(check_output([
            'http', 'post', f'http://localhost:{PORT}/visits', f'url={test_url}',
        ]).decode('utf8'))
        assert len(response) > 10
        server.kill()




def setup_parser(p):
    p.add_argument('--port', type=str, default='13131', help='Port for communicating with extension')
    p.add_argument('--config', type=Path, default=_DEFAULT_CONFIG, help='Path to config')


def main():
    setup_logzero(get_logger(), level=logging.DEBUG)
    p = argparse.ArgumentParser('wereyouhere server', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    setup_parser(p)
    args = p.parse_args()
    run(port=args.port, config=args.config)


if __name__ == '__main__':
    main()


