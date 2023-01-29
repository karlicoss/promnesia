#!/usr/bin/python3
__package__ = 'promnesia'  # ugh. hacky way to make wsgi runner work properly...

import argparse
from dataclasses import dataclass
import os
import json
from datetime import timedelta
from pathlib import Path
import logging
from functools import lru_cache
from typing import List, NamedTuple, Dict, Optional, Any, Tuple


import pytz
from pytz import BaseTzInfo

import fastapi

from sqlalchemy import MetaData, exists, literal, between, or_, and_, exc, select
from sqlalchemy import Column, Table, func, types
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql import text


from .common import PathWithMtime, DbVisit, Url, setup_logger, default_output_dir, get_system_tz
from .compat import Protocol
from .cannon import canonify


Json = Dict[str, Any]

app = fastapi.FastAPI()

# meh. need this since I don't have hooks in hug to initialize logging properly..
@lru_cache(1)
def get_logger() -> logging.Logger:
    # NOTE: uncomment to log sql queries
    # logging.basicConfig()
    # logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)

    # todo lazy log?
    logger = logging.getLogger('promnesia.server')
    setup_logger(logger, level=logging.DEBUG)

    # from hug.middleware import LogMiddleware
    # api = hug.API(__name__)
    # api.http.add_middleware(LogMiddleware(logger=logger))
    return logger


def get_version() -> str:
    from pkg_resources import get_distribution
    return get_distribution(__package__).version


class ServerConfig(NamedTuple):
    db: Path
    timezone: BaseTzInfo

    def as_str(self) -> str:
        return json.dumps({
            'timezone': self.timezone.zone,
            'db'      : str(self.db),
        })

    @classmethod
    def from_str(cls, cfgs: str) -> 'ServerConfig':
        d = json.loads(cfgs)
        return cls(
            db      =Path         (d['db']),
            timezone=pytz.timezone(d['timezone'])
        )


class EnvConfig:
    KEY = 'PROMNESIA_CONFIG'

    # apparently the only way to communicate with hug...
    @staticmethod
    @lru_cache(1)
    def get() -> ServerConfig:
        cfgs = os.environ.get(EnvConfig.KEY)
        assert cfgs is not None
        return ServerConfig.from_str(cfgs)

    @staticmethod
    def set(cfg: ServerConfig) -> None:
        os.environ[EnvConfig.KEY] = cfg.as_str()

# todo how to return exception in error?

def as_json(v: DbVisit) -> Json:
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


def get_db_path(check: bool=True) -> Path:
    db = EnvConfig.get().db
    if check:
        assert db.exists(), db
    return db


from .read_db import DbStuff, get_db_stuff

@lru_cache(1)
# PathWithMtime aids lru_cache in reloading the sqlalchemy binder
def _get_stuff(db_path: PathWithMtime) -> DbStuff:
    get_logger().debug('Reloading DB: %s', db_path)
    return get_db_stuff(db_path=db_path.path)


def get_stuff(db_path: Optional[Path]=None) -> DbStuff: # TODO better name
    # ok, it will always load from the same db file; but intermediate would be kinda an optional dump.
    if db_path is None:
        db_path = get_db_path()
    return _get_stuff(PathWithMtime.make(db_path))


def db_stats(db_path: Path) -> Json:
    engine, binder, table = get_stuff(db_path)
    query = select(func.count()).select_from(table)
    with engine.connect() as conn:
        total = list(conn.execute(query))[0][0]
    return {
        'total_visits': total,
    }


class Where(Protocol):
    def __call__(self, table: Table, url: str) -> ColumnElement[bool]:
        ...

@dataclass
class VisitsResponse:
    original_url: Url
    normalised_url: Url
    visits: Any


def search_common(url: str, where: Where) -> VisitsResponse:
    logger = get_logger()
    config = EnvConfig.get()

    logger.info('url: %s', url)
    original_url = url and url.strip()
    url = canonify(original_url)
    if not url:  # Don't eliminate a "#tag" query.
        url = original_url
    logger.info('normalised url: %s', url)

    engine, binder, table = get_stuff()

    query = table.select().where(where(table=table, url=url))
    logger.debug('query: %s', query)

    with engine.connect() as conn:
        try:
            # TODO make more defensive here
            visits: List[DbVisit] = [binder.from_row(row) for row in conn.execute(query)]
        except exc.OperationalError as e:
            if getattr(e, 'msg', None) == 'no such table: visits':
                logger.warn('you may have to run indexer first!')
                #result['visits'] = [{an error with a msg}] # TODO
                #return result
            raise

    logger.debug('got %d visits from db', len(visits))

    vlist: List[DbVisit] = []
    for vis in visits:
        dt = vis.dt
        if dt.tzinfo is None: # FIXME need this for /visits endpoint as well?
            tz = config.timezone
            dt = tz.localize(dt)
            vis = vis._replace(dt=dt)
        vlist.append(vis)

    logger.debug('responding with %d visits', len(vlist))
    # TODO respond with normalised result, then frontent could choose how to present children/siblings/whatever?
    return VisitsResponse(
        original_url=original_url,
        normalised_url=url,
        visits=list(map(as_json, vlist)),
    )


# TODO hmm, seems that the extension is using post for all requests??
# perhasp should switch to get for most endpoint
@app.get ('/status', response_model=Json)
@app.post('/status', response_model=Json)
def status() -> Json:
    '''
    Ideally, status will always respond, regardless the internal state of the backend?
    '''
    logger = get_logger()

    db = get_db_path(check=False)
    try:
        assert db.exists(), db
        db_path = str(db)
    except Exception as e:
        logger.exception(e)
        db_path = f'ERROR: db not found/unreadable (expected path {db}). You probably forgot to run indexer first. See https://github.com/karlicoss/promnesia/blob/master/doc/TROUBLESHOOTING.org'

    stats: Json
    try:
        stats = db_stats(db)
    except Exception as e:
        logger.exception(e)
        stats = {'ERROR': str(e)}

    version: Optional[str]
    try:
        version = get_version()
    except Exception as e:
        version = None

    return {
        'version': version,
        'db'     : db_path,
        'stats'  : stats,
    }


from dataclasses import dataclass
@dataclass
class VisitsRequest:
    url: Url

@app.get ('/visits', response_model=VisitsResponse)
@app.post('/visits', response_model=VisitsResponse)
def visits(request: VisitsRequest) -> VisitsResponse:
    url = request.url
    get_logger().info('/visited %s', url)
    return search_common(
        url=url,
        # odd, doesn't work just with: x or (y and z)
        where=lambda table, url: or_(
            table.c.norm_url == url,  # exact match
            and_(table.c.context != None, table.c.norm_url.startswith(url, autoescape=True)) # + child visits, but only 'interesting' ones
        ),
    )


@dataclass
class SearchRequest:
    url: Url

@app.get ('/search', response_model=VisitsResponse)
@app.post('/search', response_model=VisitsResponse)
def search(request: SearchRequest) -> VisitsResponse:
    url = request.url
    get_logger().info('/search %s', url)
    return search_common(
        url=url,
        where=lambda table, url: or_(
            # todo hmm. think about it, not sure if I need proper indexer for fuzzy search etc?
            table.c.norm_url     .contains(url, autoescape=True),
            table.c.orig_url     .contains(url, autoescape=True),
            table.c.context      .contains(url, autoescape=True),
            table.c.locator_title.contains(url, autoescape=True),
        ),
    )


@dataclass
class SearchAroundRequest:
    timestamp: float

@app.get ('/search_around', response_model=VisitsResponse)
@app.post('/search_around', response_model=VisitsResponse)
def search_around(request: SearchAroundRequest) -> VisitsResponse:
    timestamp = request.timestamp
    get_logger().info('/search_around %s', timestamp)
    utc_timestamp = timestamp # old 'timestamp' name is legacy

    # TODO meh. use count/pagination instead?
    delta_back  = timedelta(hours=3  ).total_seconds()
    delta_front = timedelta(minutes=2).total_seconds()
    # TODO not sure about delta_front.. but it also serves as quick hack to accommodate for all the truncations etc

    return search_common(
        url='http://dummy.org', # NOTE: not used in the where query (below).. perhaps need to get rid of this
        where=lambda table, url: between(
            func.strftime(
                '%s', # NOTE: it's tz aware, e.g. would distinguish +05:00 vs -03:00
                # this is a bit fragile, relies on cachew internal timestamp format, e.g.
                # 2020-11-10T06:13:03.196376+00:00 Europe/London
                func.substr(
                    table.c.dt,
                    1, # substr is 1-indexed
                    # instr finds the first match, but if not found it defaults to 0.. which we hack by concatting with ' '
                    func.instr(func.cast(table.c.dt, types.Unicode).op('||')(' '), ' ') - 1,
                    # for fucks sake.. seems that cast is necessary otherwise it tries to treat ' ' as datetime???
                )
            ) - literal(utc_timestamp),
            literal(-delta_back),
            literal(delta_front),
        ),
    )

# before 0.11.14 (including), extension didn't share the version
# so if it's not shared, assume that version
_NO_VERSION = (0, 11, 14)
_LATEST = (9999, 9999, 9999)

def as_version(version: str) -> Tuple[int, int, int]:
    if version == '':
        return _NO_VERSION
    try:
        [v1, v2, v3] = map(int, version.split('.'))
        return (v1, v2, v3)
    except Exception as e:
        logger = get_logger()
        logger.error('error while parsing version %s', version)
        logger.exception(e)
        return _LATEST


@dataclass
class VisitedRequest:
    urls: List[str]
    client_version: str = ''

VisitedResponse = List[Optional[Json]]

@app.get ('/visited', response_model=VisitedResponse)
@app.post('/visited', response_model=VisitedResponse)
def visited(request: VisitedRequest) -> VisitedResponse:
    # TODO instead switch logging to fastapi
    urls = request.urls
    client_version = request.client_version

    logger = get_logger()
    logger.info('/visited %s %s', urls, client_version)

    version = as_version(client_version)

    nurls = [canonify(u) for u in urls]
    snurls = list(sorted(set(nurls)))

    if len(snurls) == 0:
        return []

    engine, binder, table = get_stuff()

    # sqlalchemy doesn't seem to support SELECT FROM (VALUES (...)) in its api
    # also doesn't support array binding...
    # https://stackoverflow.com/questions/13190392/how-can-i-bind-a-list-to-a-parameter-in-a-custom-query-in-sqlalchemy
    bstring = ','.join(f'(:b{i})'   for i, _ in enumerate(snurls))
    bdict = {            f'b{i}': v for i, v in enumerate(snurls)}
    # TODO hopefully, visits.* thing only returns one visit??
    query = text(f"""
WITH cte(queried) AS (SELECT * FROM (values {bstring}))
SELECT queried, visits.*
    FROM cte JOIN visits
    ON queried = visits.norm_url
/*  order stuff without contexts last
    this actually doesn't make sense, locially it should be ASC??
    but somehow DESC is the one that actually works..
*/
    ORDER BY visits.context IS NULL DESC
    """).bindparams(**bdict).columns(
        Column('match', types.Unicode),
        *table.columns,
    )
    # TODO might be very beneficial for performance to have an intermediate table
    # SELECT visits.* FROM visits GROUP BY visits.norm_url ORDER BY visits.context IS NULL DESC
    # + unique index in norm_url
    # brings down large queries to 50ms...
    with engine.connect() as conn:
        res = list(conn.execute(query))
        present: Dict[str, Any] = {row[0]: binder.from_row(row[1:]) for row in res}
    results = []
    for nu in nurls:
        r = present.get(nu, None)
        results.append(None if r is None else as_json(r))

    # no need for it anymore, extension has been updated since
    # just keeping as an example
    # if version <= (0, 11, 14):
    #     # older extension versions expected boolean result here
    #     results = [r is not None for r in results] # type: ignore[misc]

    return results


def _run(*, host: str, port: str, quiet: bool, config: ServerConfig) -> None:
    logger = get_logger()

    logger.info('Running server with %s', config)

    EnvConfig.set(config)

    import uvicorn
    uvicorn.run('promnesia.server:app', host=host, port=int(port), log_level='debug')


def run(args: argparse.Namespace) -> None:
    _run(
        port=args.port,
        host=args.host,
        quiet=args.quiet,
        config=ServerConfig(
            db=args.db,
            timezone=args.timezone,
        )
    )


def default_db_path() -> Path:
    return default_output_dir() / 'promnesia.sqlite'


def setup_parser(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        '--host',
        type=str,
        # TODO hmm it's a somewhat unfortunate default..
        # but for now at least keeping it for compatibility with old hug runner
        # otherwise Promnesia might stop working for people who upgrade it
        default='0.0.0.0',
        help='Local IP to listen on',
    )

    p.add_argument(
        '--port',
        type=str,
        default='13131',
        help='Port for communicating with extension',
    )

    p.add_argument(
        '--quiet',
        action='store_true',
        help='Pass to log less',
    )
    # TODO need to keep consistent with the backend...
    # todo use output_dir instead?
    p.add_argument(
        '--db',
        type=Path,
        default=default_db_path(),
        help='Path to the links database (optional, uses user data dir by default)',
    )

    p.add_argument(
        '--timezone',
        type=pytz.timezone,
        default=get_system_tz(),
        help='Fallback timezone, defaults to the system timezone if not specified',
    )
