from __future__ import annotations

from pathlib import Path
from typing import Tuple

from sqlalchemy import (
    Engine,
    Index,
    MetaData,
    Table,
    create_engine,
    exc,
)

from .common import DbVisit, get_columns, row_to_db_visit

DbStuff = Tuple[Engine, Table]


def get_db_stuff(db_path: Path) -> DbStuff:
    assert db_path.exists(), db_path
    # todo how to open read only?
    # actually not sure if we can since we are creating an index here
    engine = create_engine(f'sqlite:///{db_path}')  # , echo=True)

    meta = MetaData()
    table = Table('visits', meta, *get_columns())

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
    return engine, table


def get_all_db_visits(db_path: Path) -> list[DbVisit]:
    # NOTE: this is pretty inefficient if the DB is huge
    # mostly intended for tests
    engine, table = get_db_stuff(db_path)
    query = table.select()
    with engine.connect() as conn:
        res = [row_to_db_visit(row) for row in conn.execute(query)]
    engine.dispose()
    return res
