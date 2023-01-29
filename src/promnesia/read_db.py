from pathlib import Path
from typing import Tuple, List

from cachew import NTBinder
from sqlalchemy import (
    create_engine,
    exc,
    MetaData,
    Index,
    Table,
)
from sqlalchemy.engine import Engine

from .common import DbVisit


DbStuff = Tuple[Engine, NTBinder, Table]


def get_db_stuff(db_path: Path) -> DbStuff:
    assert db_path.exists(), db_path
    # todo how to open read only?
    # actually not sure if we can since we are creating an index here
    engine = create_engine(f'sqlite:///{db_path}') # , echo=True)

    binder = NTBinder.make(DbVisit)

    meta = MetaData()
    table = Table('visits', meta, *binder.columns)

    idx = Index('index_norm_url', table.c.norm_url)
    try:
        idx.create(bind=engine)
    except exc.OperationalError as e:
        if 'already exists' in str(e):
            # meh, but no idea how to check it properly...
            pass
        else:
            raise e

    # NOTE: apparently it's ok to open connection on every request? at least my comparisons didn't show anything
    return engine, binder, table


def get_all_db_visits(db_path: Path) -> List[DbVisit]:
    # NOTE: this is pretty inefficient if the DB is huge
    # mostly intended for tests
    engine, binder, table = get_db_stuff(db_path)
    query = table.select()
    with engine.connect() as conn:
        return [binder.from_row(row) for row in conn.execute(query)]
