import os
from pathlib import Path
import shutil
from typing import Dict, List, Tuple, Set, Iterable

from more_itertools import chunked

from sqlalchemy import create_engine, MetaData # type: ignore
from sqlalchemy import Column, Table # type: ignore

from cachew import NTBinder

from .common import get_logger, DbVisit, get_tmpdir, Res, now_tz, Loc
from . import config


def update_policy_active() -> bool:
    # NOTE: experimental.. need to make it a proper cmdline argument later
    INDEX_POLICY = os.environ.get('PROMNESIA_INDEX_POLICY', 'overwrite_all')
    # if 'update' is passed, will run against the existing db and only tough the sources present in the current index run
    # not sue if a good name for this..
    return INDEX_POLICY == 'update'


# NOTE: I guess the main performance benefit from this is not creating too many tmp lists and avoiding overhead
# since as far as sql is concerned it should all be in the same transaction. only a guess
# not sure it's the proper way to handle it
# see test_index_many
_CHUNK_BY = 10


# returns critical warnings
def visits_to_sqlite(vit: Iterable[Res[DbVisit]]) -> List[Exception]:
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
    policy_update = update_policy_active()
    if not policy_update:
        engine = create_engine(f'sqlite:///{tpath}')
    else:
        engine = create_engine(f'sqlite:///{db_path}')

    binder = NTBinder.make(DbVisit)
    meta = MetaData(engine)
    table = Table('visits', meta, *binder.columns)
    meta.create_all()

    cleared: Set[str] = set()
    with engine.begin() as conn:
        for chunk in chunked(vit_ok(), n=_CHUNK_BY):
            srcs = set(v.src or '' for v in chunk)
            new = srcs.difference(cleared)
            for src in new:
                conn.execute(table.delete().where(table.c.src == src))
                cleared.add(src)

            bound = [binder.to_row(x) for x in chunk]
            # pylint: disable=no-value-for-parameter
            conn.execute(table.insert().values(bound))

    if not policy_update:
        shutil.move(str(tpath), str(db_path))

    errs = '' if errors == 0 else f', {errors} ERRORS'
    total = ok + errors
    what = 'updated' if policy_update else 'overwritten'
    logger.info('%s database "%s". %d total (%d OK%s)', what, db_path, total, ok, errs)
    res: List[Exception] = []
    if total == 0:
        res.append(RuntimeError('No visits were indexed, something is probably wrong!'))
    return res
