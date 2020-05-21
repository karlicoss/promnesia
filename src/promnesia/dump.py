from pathlib import Path
from typing import Dict, List, Tuple
import shutil

from more_itertools import chunked

from sqlalchemy import create_engine, MetaData # type: ignore
from sqlalchemy import Column, Table # type: ignore

from cachew import NTBinder

from .common import get_logger, DbVisit, get_tmpdir
from . import config


# NOTE: I guess the main performance benefit from this is not creating too many tmp lists and avoiding overhead
# since as far as sql is concerned it should all be in the same transaction. only a guess
# not sure it's the proper way to handle it
# see test_index_many
_CHUNK_BY = 10


def dump_histories(all_histories: List[Tuple[str, List[DbVisit]]]) -> None:
    logger = get_logger()
    output_dir = Path(config.get().OUTPUT_DIR)
    db_path = output_dir / 'promnesia.sqlite'

    def iter_visits():
        for e, h in all_histories:
            # TODO sort them somehow for determinism?
            # TODO what do we do with errors?
            # TODO maybe conform them to schema and dump too?
            # TODO or, dump to a separate table?
            yield from h

    tpath = Path(get_tmpdir().name) / 'promnesia.tmp.sqlite'
    engine = create_engine(f'sqlite:///{tpath}')
    binder = NTBinder.make(DbVisit)
    meta = MetaData(engine)
    table = Table('visits', meta, *binder.columns)
    meta.create_all()

    with engine.begin() as conn:
        for chunk in chunked(iter_visits(), n=_CHUNK_BY):
            bound = [binder.to_row(x) for x in chunk]
            # pylint: disable=no-value-for-parameter
            conn.execute(table.insert().values(bound))

    shutil.move(str(tpath), str(db_path))

    logger.info('saved database to %s', db_path)
