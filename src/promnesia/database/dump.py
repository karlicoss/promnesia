from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from more_itertools import chunked
from sqlalchemy import (
    Engine,
    MetaData,
    Table,
    create_engine,
    event,
    exc,
    func,
    select,
)
from sqlalchemy.dialects import sqlite as dialect_sqlite

from .. import config
from ..common import (
    DbVisit,
    Loc,
    Res,
    SourceName,
    get_logger,
    now_tz,
)
from .common import db_visit_to_row, get_columns

# NOTE: I guess the main performance benefit from this is not creating too many tmp lists and avoiding overhead
# since as far as sql is concerned it should all be in the same transaction. only a guess
# not sure it's the proper way to handle it
# see test_index_many
_CHUNK_BY = 10

# I guess 1 hour is definitely enough
_CONNECTION_TIMEOUT_SECONDS = 3600

SRC_ERROR = 'error'


# using WAL keeps database readable while we're writing in it
# this is tested by test_query_while_indexing
def enable_wal(dbapi_con, con_record) -> None:
    dbapi_con.execute('PRAGMA journal_mode = WAL')


def begin_immediate_transaction(conn):
    conn.exec_driver_sql('BEGIN IMMEDIATE')


Stats = dict[SourceName | None, int]


# returns critical warnings
def visits_to_sqlite(
    vit: Iterable[Res[DbVisit]],
    *,
    overwrite_db: bool,
    _db_path: Path | None = None,  # only used in tests
) -> list[Exception]:
    if _db_path is None:
        db_path = config.get().db
    else:
        db_path = _db_path

    logger = get_logger()

    now = now_tz()

    index_stats: Stats = {}

    def vit_ok() -> Iterable[DbVisit]:
        for v in vit:
            ev: DbVisit
            if isinstance(v, DbVisit):
                ev = v
            else:
                # conform to the schema and dump. can't hurt anyway
                ev = DbVisit(
                    norm_url='<error>',
                    orig_url='<error>',
                    dt=now,
                    locator=Loc.make('<errror>'),
                    src=SRC_ERROR,
                    # todo attach backtrace?
                    context=repr(v),
                )
            index_stats[ev.src] = index_stats.get(ev.src, 0) + 1
            yield ev

    meta = MetaData()
    table = Table('visits', meta, *get_columns())

    def query_total_stats(conn) -> Stats:
        query = select(table.c.src, func.count(table.c.src)).select_from(table).group_by(table.c.src)
        return dict(conn.execute(query).all())

    def get_engine(*args, **kwargs) -> Engine:
        # kwargs['echo'] = True  # useful for debugging
        e = create_engine(*args, **kwargs)
        event.listen(e, 'connect', enable_wal)
        return e

    ### use readonly database just to get stats
    pengine = get_engine('sqlite://', creator=lambda: sqlite3.connect(f"file:{db_path}?mode=ro", uri=True))
    stats_before: Stats
    try:
        with pengine.begin() as conn:
            stats_before = query_total_stats(conn)
    except exc.OperationalError as oe:
        if oe.code == 'e3q8':
            # db doesn't exist yet
            stats_before = {}
        else:
            raise oe
    pengine.dispose()
    ###

    # needtimeout, othewise concurrent indexing might not work
    # (note that this also requires WAL mode)
    engine = get_engine(f'sqlite:///{db_path}', connect_args={'timeout': _CONNECTION_TIMEOUT_SECONDS})

    cleared: set[str] = set()

    # by default, sqlalchemy does some sort of BEGIN (implicit) transaction, which doesn't provide proper isolation??
    # see https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl
    event.listen(engine, 'begin', begin_immediate_transaction)
    # TODO to allow more concurrent indexing, maybe could instead write to a temporary table?
    # or collect visits first and only then start writing to the db to minimize db access window.. not sure

    # engine.begin() starts a transaction
    # so everything inside this block will be atomic to the outside observers
    with engine.begin() as conn:
        table.create(conn, checkfirst=True)

        if overwrite_db:
            conn.execute(table.delete())

        insert_stmt = table.insert()
        # using raw statement gives a massive speedup for inserting visits
        # see test_benchmark_visits_dumping
        insert_stmt_raw = str(insert_stmt.compile(dialect=dialect_sqlite.dialect(paramstyle='qmark')))

        for chunk in chunked(vit_ok(), n=_CHUNK_BY):
            srcs = {v.src or '' for v in chunk}
            new = srcs.difference(cleared)

            for src in new:
                conn.execute(table.delete().where(table.c.src == src))
                cleared.add(src)

            bound = [db_visit_to_row(v) for v in chunk]
            conn.exec_driver_sql(insert_stmt_raw, bound)

        stats_after = query_total_stats(conn)
    engine.dispose()

    stats_changes = {}
    # map str just in case some srcs are None
    for k in sorted(map(str, {*stats_before.keys(), *stats_after.keys()})):
        diff = stats_after.get(k, 0) - stats_before.get(k, 0)
        if diff == 0:
            continue
        sdiff = ('+' if diff > 0 else '') + str(diff)
        stats_changes[k] = sdiff

    action = 'overwritten' if overwrite_db else 'updated'
    total_indexed = sum(index_stats.values())
    total_err = index_stats.get(SRC_ERROR, 0)
    total_ok = total_indexed - total_err
    logger.info(f'indexed (current run) : total: {total_indexed}, ok: {total_ok}, errors: {total_err} {index_stats}')
    logger.info(f'database "{db_path}" : {action}')
    logger.info(f'database stats before : {stats_before}')
    logger.info(f'database stats after  : {stats_after}')

    if len(stats_changes) == 0:
        logger.info('database stats changes: no changes')
    else:
        for k, v in stats_changes.items():
            logger.info(f'database stats changes: {k} {v}')

    res: list[Exception] = []
    if total_ok == 0:
        res.append(RuntimeError('No visits were indexed, something is probably wrong!'))
    return res
