#!/usr/bin/python3
__package__ = 'wereyouhere' # ugh. hacky way to make hug work properly...

import argparse
import os
import sys
from datetime import timedelta, datetime
from pathlib import Path
import logging
from functools import lru_cache
from typing import Collection, List, NamedTuple, Dict

from kython import setup_logzero

import hug # type: ignore
import hug.types as T # type: ignore


from .common import PathWithMtime, Config, Visit, Url, import_config, Loc
from .normalise import normalise_url

_ENV_CONFIG = 'WEREYOUHERE_CONFIG'

# meh. need this since I don't have hooks in hug to initialize logging properly..
@lru_cache(1)
def get_logger():
    logger = logging.getLogger('wereyouhere')
    setup_logzero(logger, level=logging.DEBUG)
    return logger


@lru_cache(1)
def _load_config(mpath: PathWithMtime) -> Config:
    return import_config(mpath.path)


def load_config() -> Config:
    cp = os.environ.get(_ENV_CONFIG)
    assert cp is not None
    return _load_config(PathWithMtime.make(Path(cp)))

# TODO use that?? https://github.com/timothycrosley/hug/blob/develop/tests/test_async.py

    # def reg_visit(v):
    #     # TODO parse loc
    #     for vis in v['visits']:
    #         dt = fromisoformat(vis['dt'])
    #         if dt.tzinfo is None:
    #             dt = config.FALLBACK_TIMEZONE.localize(dt)

    #         ld = vis['locator']
    #         loc = Loc(file=ld['file'], line=ld['line'])


# TODO how to return exception in error?

def as_json(v: Visit) -> Dict:
   #  "09 Aug 2018 19:48",
   #  "06 Aug 2018 21:36--21:37",
    # TODO perhaps tag merging should be done by browser as well?
    # TODO also local should be suppressed if any other tag with this timestamp is present
    dts = v.dt.strftime('%d %b %Y %H:%M')
    loc = v.locator
    # TODO is locator always present??
    locs = loc.file + (':' + str(loc.line) if loc.line is not None else '')
    return {
        # TODO do not display year if it's current year??
        'dt': dts,
        'tags': [v.tag],
        'context': v.context,
        'locator': locs,
    }

from sqlalchemy import create_engine, MetaData # type: ignore
from sqlalchemy import Column, Table # type: ignore

from kython.kcache import Binder

class XVisit(NamedTuple):
    url: str
    dt: datetime
    context: str
    tag: str
    # TODO locator?


@lru_cache(1)
def get_stuff(): # TODO better name
    # ok, it will always load from the same db file; but intermediate would be kinda an optional dump.
    config = load_config()
    db_path = Path(config.OUTPUT_DIR) / 'visits.sqlite' # TODO FIXME need to update it
    assert db_path.exists()

    # TODO how to open read only?
    engine = create_engine(f'sqlite:///{db_path}')

    binder = Binder(clazz=XVisit)

    meta = MetaData(engine) # , reflect=True) # TODO what does reflect do?
    table = Table('visits', meta, *binder.columns)
    meta.create_all()

    return engine, binder, table


@hug.local()
@hug.post('/visits')
def visits(
        url: T.text,
):
    logger = get_logger()
    config = load_config()

    logger.info('url: %s', url)
    url = normalise_url(url)
    logger.info('normalised url: %s', url)

    engine, binder, table = get_stuff()

    query = table.select().where(table.c.url == url)

    with engine.connect() as conn:
        rows = conn.execute(query)
        visits = [binder.from_row(row) for row in rows]

    logger.debug('got %d visits from db', len(visits))

    vlist = []
    for vis in visits:
        dt = vis.dt
        if dt.tzinfo is None:
            dt = config.FALLBACK_TIMEZONE.localize(dt)
        loc = Loc(file="TODO", line=None) # TODO FIXME, that'
        vlist.append(Visit(
            dt=dt,
            locator=loc,
            context=vis.context,
            tag=vis.tag,
        ))
    if len(vlist) is None:
        return None # TODO handle empty list in client?
    else:
        return list(map(as_json, vlist))


@hug.local()
@hug.post('/visited')
def visited(
        urls, # TODO type
):
    logger = get_logger()

    nurls = list(map(normalise_url, urls))
    logger.debug(nurls)

    raise RuntimeError("TODO FIXME")
    # vmap = get_state()
    # return [
    #     u in vmap for u in nurls
    # ]


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


# def test_load():
#     state = get_state(get_latest_db(Path('test_config.py')))
#     from pprint import pprint
#     pprint(state)


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
        print("Giving 5 secs to start server up")
        time.sleep(5)
        print("Started server up")
        # TODO which url??

        for q in range(3):
            print(f"querying {q}")
            test_url = 'https://slatestarcodex.com/2014/03/17/what-universal-human-experiences-are-you-missing-without-realizing-it/'
            response = json.loads(check_output([
                'http', 'post', f'http://localhost:{PORT}/visits', f'url={test_url}',
            ]).decode('utf8'))
            assert len(response) > 10
        print("DONE!!!!")
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


