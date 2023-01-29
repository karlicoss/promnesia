from pathlib import Path
import shutil
from typing import  List, Set, Iterable

from more_itertools import chunked

from sqlalchemy import create_engine, MetaData, Table, event, text

from cachew import NTBinder

from .common import get_logger, DbVisit, get_tmpdir, Res, now_tz, Loc
from . import config


# NOTE: I guess the main performance benefit from this is not creating too many tmp lists and avoiding overhead
# since as far as sql is concerned it should all be in the same transaction. only a guess
# not sure it's the proper way to handle it
# see test_index_many
_CHUNK_BY = 10

# I guess 1 hour is definitely enough
_CONNECTION_TIMEOUT_SECONDS = 3600

# returns critical warnings
def visits_to_sqlite(vit: Iterable[Res[DbVisit]], *, overwrite_db: bool) -> List[Exception]:
    logger = get_logger()
    db_path = config.get().db

    now = now_tz()
    ok = 0
    errors = 0
    def vit_ok() -> Iterable[DbVisit]:
        nonlocal errors, ok
        for v in vit:
            if isinstance(v, DbVisit):
                ok += 1
                yield v
            else:
                errors += 1
                # conform to the schema and dump. can't hurt anyway
                ev = DbVisit(
                    norm_url='<error>',
                    orig_url='<error>',
                    dt=now,
                    locator=Loc.make('<errror>'),
                    src='error',
                    # todo attach backtrace?
                    context=repr(v),
                )
                yield ev

    tpath = Path(get_tmpdir().name) / 'promnesia.tmp.sqlite'
    if overwrite_db:
        # here we don't need timeout, since it's a brand new DB
        engine = create_engine(f'sqlite:///{tpath}')
    else:
        # here we need a timeout, othewise concurrent indexing might not work
        # (note that this also needs WAL mode)
        # see test_concurrent_indexing
        engine = create_engine(f'sqlite:///{db_path}', connect_args={'timeout': _CONNECTION_TIMEOUT_SECONDS})

    # using WAL keeps database readable while we're writing in it
    # this is tested by test_query_while_indexing
    def enable_wal(dbapi_con, con_record) -> None:
        dbapi_con.execute('PRAGMA journal_mode = WAL')
    event.listen(engine, 'connect', enable_wal)

    binder = NTBinder.make(DbVisit)
    meta = MetaData()
    table = Table('visits', meta, *binder.columns)

    cleared: Set[str] = set()
    ncleared = 0
    with engine.begin() as conn:
        table.create(conn, checkfirst=True)

        for chunk in chunked(vit_ok(), n=_CHUNK_BY):
            srcs = set(v.src or '' for v in chunk)
            new = srcs.difference(cleared)

            for src in new:
                conn.execute(table.delete().where(table.c.src == src))
                cursor = conn.execute(text("SELECT changes()")).fetchone()
                assert cursor is not None
                ncleared += cursor[0]
                cleared.add(src)

            bound = [binder.to_row(x) for x in chunk]
            # pylint: disable=no-value-for-parameter
            conn.execute(table.insert().values(bound))
    engine.dispose()

    if overwrite_db:
        shutil.move(str(tpath), str(db_path))

    errs = '' if errors == 0 else f', {errors} ERRORS'
    total = ok + errors
    what = 'overwritten' if overwrite_db else 'updated'
    logger.info(
        '%s database "%s". %d total (%d OK%s, %d cleared, +%d more)',
        what, db_path, total, ok, errs, ncleared, ok - ncleared)
    res: List[Exception] = []
    if total == 0:
        res.append(RuntimeError('No visits were indexed, something is probably wrong!'))
    return res
