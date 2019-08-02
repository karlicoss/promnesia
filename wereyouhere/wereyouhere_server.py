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

from cachew import DbBinder

import hug # type: ignore
import hug.types as T # type: ignore

from sqlalchemy import create_engine, MetaData, exists, literal, between # type: ignore
from sqlalchemy import Column, Table, func # type: ignore


from .common import PathWithMtime, DbVisit, Url, Loc
from .config import Config, import_config
from .normalise import normalise_url

_ENV_CONFIG = 'WEREYOUHERE_CONFIG'


# TODO not sure about utc in database... keep orig timezone?

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


# TODO how to return exception in error?

def as_json(v: DbVisit) -> Dict:
    # TODO check utc
   #  "09 Aug 2018 19:48",
   #  "06 Aug 2018 21:36--21:37",
    # TODO perhaps tag merging should be done by browser as well?
    # TODO also local should be suppressed if any other tag with this timestamp is present
    dts = v.dt.strftime('%d %b %Y %H:%M')
    loc = v.locator
    # # TODO is locator always present??
    return {
        # TODO do not display year if it's current year??
        'dt': dts,
        'tags': [v.tag],
        'context': v.context,
        'duration': v.duration,
        'locator': {
            'title': loc.title,
            'href' : loc.href,
        },
        'original_url'  : v.orig_url,
        'normalised_url': v.norm_url,
    }

@lru_cache(1)
def get_stuff(): # TODO better name
    # ok, it will always load from the same db file; but intermediate would be kinda an optional dump.
    config = load_config()
    db_path = Path(config.OUTPUT_DIR) / 'visits.sqlite' # TODO FIXME need to update it
    assert db_path.exists()

    # TODO how to open read only?
    engine = create_engine(f'sqlite:///{db_path}') # , echo=True)

    binder = DbBinder(DbVisit)

    meta = MetaData(engine)
    table = Table('visits', meta, *binder.db_columns)

    return engine, binder, table


def search_common(url: str, where):
    logger = get_logger()
    config = load_config()

    logger.info('url: %s', url)
    url = normalise_url(url)
    logger.info('normalised url: %s', url)

    engine, binder, table = get_stuff()

    query = table.select().where(where(table=table, url=url))

    logger.info('query: %s', query)

    with engine.connect() as conn:
        visits = [binder.from_row(row) for row in conn.execute(query)]

    logger.debug('got %d visits from db', len(visits))

    vlist = []
    for vis in visits:
        dt = vis.dt
        if dt.tzinfo is None:
            # TODO hmm. I guess server and indexer should better agree on timezone...
            # TODO use lazy property in cofig for extractors?
            dt = config.FALLBACK_TIMEZONE.localize(dt)
            vis = vis._replace(dt=dt)
        vlist.append(vis)

    logger.debug('responding with %d visits', len(vlist))
    if len(vlist) is None:
        return None # TODO handle empty list in client?
    else:
        return list(map(as_json, vlist))


@hug.local()
@hug.post('/visits')
def visits(
        url: T.text,
):
    return search_common(
        url=url,
        where=lambda table, url: table.c.norm_url == url,
    )


@hug.local()
@hug.post('/search')
def search(
        url: T.text
):
    # TODO rely on hug logger for query
    return search_common(
        url=url,
        where=lambda table, url: table.c.norm_url.like('%' + url + '%'), # TODO FIXME what if url contains %? (and it will!)
    )


@hug.local()
@hug.post('/search_around')
def search_around(
        timestamp: T.number,
):
    delta_back  = timedelta(hours=3).total_seconds()
    delta_front = timedelta(minutes=5).total_seconds()
    # TODO not sure about front.. but it also serves as quick hack to accomodate for all the truncations etc
    return search_common(
        url='http://dummy.org', # TODO remove it from search_common
        # TODO no abs?
        where=lambda table, url: between(
            func.strftime('%s', func.datetime(table.c.dt)) - literal(timestamp),
            literal(-delta_back),
            literal(delta_front),
        ),
    )

@hug.local()
@hug.post('/visited')
def visited(
        urls, # TODO type
):
    logger = get_logger()

    logger.debug(urls)
    nurls = list(map(normalise_url, urls))
    logger.debug('normalised: %s', nurls)

    engine, binder, table = get_stuff()

    # sqlalchemy doesn't seem to support SELECT FROM (VALUES (...)) in its api
    # also doesn't support array binding...
    # https://stackoverflow.com/questions/13190392/how-can-i-bind-a-list-to-a-parameter-in-a-custom-query-in-sqlalchemy
    bstring = ','.join(f'(:b{i})'   for i, _ in enumerate(nurls))
    bdict = {            f'b{i}': v for i, v in enumerate(nurls)}

    query = f"""
WITH cte(queried) AS (SELECT * FROM (values {bstring}))
SELECT visits.norm_url
    FROM cte LEFT JOIN visits
    ON visits.norm_url = queried
    """
    with engine.connect() as conn:
        res = list(conn.execute(query, bdict))
        results = [x[0] is not None for x in res]
    return results


def run(port: str, config: Path, quiet: bool):
    logger = get_logger()
    env = os.environ.copy()
    # # not sure if there is a simpler way to communicate with the server...
    env[_ENV_CONFIG] = str(config)
    args = [
        'wereyouhere-server',
        *(['--silent'] if quiet else []),
        '-p', port,
        '-f', __file__,
    ]
    logger.info('Running server: %s', args)
    os.execvpe('hug', args, env)


_DEFAULT_CONFIG = Path('config.py')


def setup_parser(p):
    p.add_argument('--port', type=str, default='13131', help='Port for communicating with extension')
    p.add_argument('--config', type=Path, default=_DEFAULT_CONFIG, help='Path to config')
    p.add_argument('--quiet', action='store_true')


def main():
    # setup_logzero(logging.getLogger('sqlalchemy.engine'), level=logging.DEBUG)
    setup_logzero(get_logger(), level=logging.DEBUG)
    p = argparse.ArgumentParser('wereyouhere server', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    setup_parser(p)
    args = p.parse_args()
    run(port=args.port, config=args.config, quiet=args.quiet)


if __name__ == '__main__':
    main()


