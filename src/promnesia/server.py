#!/usr/bin/python3
__package__ = 'promnesia'  # ugh. hacky way to make hug work properly...

import os
import json
from datetime import timedelta, datetime
from pathlib import Path
import logging
from functools import lru_cache
from typing import Collection, List, NamedTuple, Dict, Optional


from cachew import NTBinder

import pytz
from pytz.tzinfo import BaseTzInfo # type: ignore

import hug # type: ignore
import hug.types as T # type: ignore

from sqlalchemy import create_engine, MetaData, exists, literal, between, or_, and_ # type: ignore
from sqlalchemy import Column, Table, func # type: ignore


from .common import PathWithMtime, DbVisit, Url, Loc, setup_logger, PathIsh
from .cannon import canonify

_ENV_CONFIG = 'PROMNESIA_CONFIG'


# TODO not sure about utc in database... keep orig timezone?

# meh. need this since I don't have hooks in hug to initialize logging properly..
@lru_cache(1)
def get_logger():
    logger = logging.getLogger('promnesia')
    setup_logger(logger, level=logging.DEBUG)
    return logger


def get_version() -> str:
    from pkg_resources import get_distribution
    return get_distribution('promnesia').version


class ServerConfig(NamedTuple):
    db: Path
    timezone: BaseTzInfo

    @classmethod
    def make(cls, db: PathIsh, timezone: str) -> 'ServerConfig':
        tz = pytz.timezone(timezone)
        return cls(db=Path(db), timezone=tz)


@lru_cache(1)
def get_config() -> ServerConfig:
    cfg = os.environ.get(_ENV_CONFIG)
    assert cfg is not None
    return ServerConfig.make(**json.loads(cfg))


# TODO use that?? https://github.com/timothycrosley/hug/blob/develop/tests/test_async.py

# TODO how to return exception in error?

def as_json(v: DbVisit) -> Dict:
    # yep, this is NOT %Y-%m-%d as is seems to be the only format with timezone that Date.parse in JS accepts. Just forget it.
    dts = v.dt.strftime('%d %b %Y %H:%M:%S %z')
    loc = v.locator
    # TODO is locator always present??
    return {
        # TODO do not display year if it's current year??
        'dt': dts,
        # TODO the frontend had some bug with handling empty string as src. fix that later
        'src': v.src or 'unnamed',
        'context': v.context,
        'duration': v.duration,
        'locator': {
            'title': loc.title,
            'href' : loc.href,
        },
        'original_url'  : v.orig_url,
        'normalised_url': v.norm_url,
    }


def get_db_path() -> Path:
    config = get_config()
    db = config.db
    assert db.exists(), db
    return db


# TODO maybe, keep db connection? need to recycle it properly..
@lru_cache(1)
# PathWithMtime aids lru_cache in reloading the sqlalchemy binder
def _get_stuff(db_path: PathWithMtime):
    get_logger().info('Reloading DB: %s', db_path)
    # TODO how to open read only?
    engine = create_engine(f'sqlite:///{db_path.path}') # , echo=True)

    binder = NTBinder.make(DbVisit)

    meta = MetaData(engine)
    table = Table('visits', meta, *binder.columns)

    return engine, binder, table


def get_stuff(db_path=None): # TODO better name
    # ok, it will always load from the same db file; but intermediate would be kinda an optional dump.
    if db_path is None:
        db_path = get_db_path()
    return _get_stuff(PathWithMtime.make(db_path))



def search_common(url: str, where):
    logger = get_logger()
    config = get_config()

    logger.info('url: %s', url)
    original_url = url
    url = canonify(url)
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
            tz = config.timezone
            dt = tz.localize(dt)
            vis = vis._replace(dt=dt)
        vlist.append(vis)

    logger.debug('responding with %d visits', len(vlist))
    # TODO respond with normalised result, then frontent could choose how to present children/siblings/whatever?
    return {
        'orginal_url'   : original_url,
        'normalised_url': url,
        'visits': list(map(as_json, vlist)),
    }


@hug.local()
@hug.post('/status')
def status():
    '''
    Ideally, status will always respond, regardless the internal state of the backend?
    '''
    # TODO hug stats?

    db_path: Optional[str]
    try:
        db_path = str(get_db_path())
        # TODO use 'db_stats' instead? add count or something else
    except Exception as e:
        # TODO not sure how to properly communicate the error to frontend?
        db_path = None

    version: Optional[str]
    try:
        version = get_version()
    except Exception as e:
        version = None

    return {
        'db'     : db_path,
        'version': version,
    }
# TODO might be good to include the frontend version in the requests?


@hug.local()
@hug.post('/visits')
def visits(
        url: T.text,
):
    return search_common(
        url=url,
        # odd, doesn't work just with: x or (y and z)
        where=lambda table, url: or_(
            table.c.norm_url == url,
            and_(table.c.context != None, table.c.norm_url.startswith(url, autoescape=True))
        ),
    )


@hug.local()
@hug.post('/search')
def search(
        url: T.text
):
    # TODO rely on hug logger for query
    return search_common(
        url=url,
        where=lambda table, url: or_(
            table.c.norm_url.contains(url, autoescape=True),
            # TODO hmm. think about it, not sure if I need proper indexer for fuzzy search etc?
            table.c.context.contains(url, autoescape=True),
        ),
    )


@hug.local()
@hug.post('/search_around')
def search_around(
        timestamp: T.number,
):
    utc_timestamp = timestamp # old 'timestamp' name is legacy

    # TODO meh. use count instead?
    delta_back  = timedelta(hours=3).total_seconds()
    delta_front = timedelta(minutes=2).total_seconds()
    # TODO not sure about front.. but it also serves as quick hack to accomodate for all the truncations etc
    return search_common(
        url='http://dummy.org', # TODO remove it from search_common
        where=lambda table, url: between(
            # %s is a unix timestamp
            # TODO careful.. not sure how datetime works w.r.t. datetime string without the timezone info..
            func.strftime('%s', func.datetime(table.c.dt)) - literal(utc_timestamp),
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
    norms = [(u, canonify(u)) for u in urls]
    # logger.debug('\n'.join(f'{u} -> {nu}' for u, nu in norms))

    nurls = [n[1] for n in norms]
    engine, binder, table = get_stuff()

    snurls = list(sorted(set(nurls)))
    # sqlalchemy doesn't seem to support SELECT FROM (VALUES (...)) in its api
    # also doesn't support array binding...
    # https://stackoverflow.com/questions/13190392/how-can-i-bind-a-list-to-a-parameter-in-a-custom-query-in-sqlalchemy
    bstring = ','.join(f'(:b{i})'   for i, _ in enumerate(snurls))
    bdict = {            f'b{i}': v for i, v in enumerate(snurls)}

    query = f"""
WITH cte(queried) AS (SELECT * FROM (values {bstring}))
SELECT queried
    FROM cte JOIN visits
    ON queried = visits.norm_url
    """
    # hmm that was quite slow...
    # SELECT queried FROM cte WHERE EXISTS (SELECT 1 FROM visits WHERE queried = visits.norm_url)
    logger.debug(bdict)
    logger.debug(query)
    with engine.connect() as conn:
        res = list(conn.execute(query, bdict))
        present = {x[0] for x in res}
    results = [nu in present for nu in nurls]

    # logger.debug('\n'.join(
    #     f'{"X" if v else "-"} {u} -> {nu}' for v, (u, nu) in zip(results, norms)
    # ))
    return results


def _run(*, port: str, db: Path, timezone: str, quiet: bool):
    logger = get_logger()
    env = {
        **os.environ,
        # not sure if there is a simpler way to communicate with hug..
        _ENV_CONFIG: json.dumps({'db': str(db), 'timezone': timezone}),
    }
    args = [
        'python3',
        '-m', 'hug', # TODO eh, not sure about this. what if user had it already installed?? it's a mess..
        *(['--silent'] if quiet else []),
        '-p', port,
        '-f', __file__,
    ]
    logger.info('Running server: %s', args)
    os.execvpe('python3', args, env)


def run(args):
    _run(port=args.port, db=args.db, timezone=args.timezone, quiet=args.quiet)


_DEFAULT_CONFIG = Path('config.py')


def get_system_tz() -> str:
    logger = get_logger()
    try:
        import tzlocal # type: ignore
        return tzlocal.get_localzone().zone
    except Exception as e:
        logger.exception(e)
        logger.error("Couldn't determine system timezone. Falling back to UTC. Please report this as a bug!")
        return 'UTC'


# TODO rename to 'backend'?
def setup_parser(p):
    p.add_argument('--port'    , type=str , default='13131', help='Port for communicating with extension')
    # TODO mm. should add fallback timezone to frontend instead I guess?
    p.add_argument('--db'      , type=Path, required=True  , help='Path to the link database (required)')
    p.add_argument('--timezone', type=str , default=get_system_tz(), help='Fallback timezone, defaults to the system timezone if not specified')
    p.add_argument('--quiet'              , action='store_true', help='Less logging')

