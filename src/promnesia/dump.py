from pathlib import Path
from typing import Dict, List, Tuple
import shutil

from sqlalchemy import create_engine, MetaData # type: ignore
from sqlalchemy import Column, Table # type: ignore

from cachew import NTBinder, ichunks

from .common import get_logger, DbVisit, get_tmpdir
from . import config


def dump_histories(all_histories: List[Tuple[str, List[DbVisit]]]):
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
        for chunk in ichunks(iter_visits(), n=1000):
            bound = [binder.to_row(x) for x in chunk]
            # pylint: disable=no-value-for-parameter
            conn.execute(table.insert().values(bound))

    shutil.move(str(tpath), str(db_path))

    logger.info('saved database to %s', db_path)
