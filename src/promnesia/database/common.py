from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import (
    Column,
    Integer,
    String,
)

# TODO maybe later move DbVisit here completely?
# kinda an issue that it's technically an "api" because hook in config can patch up DbVisit
from ..common import DbVisit, Loc


def get_columns() -> Sequence[Column]:
    # fmt: off
    res: Sequence[Column] = [
        Column('norm_url'     , String()),
        Column('orig_url'     , String()),
        Column('dt'           , String()),
        Column('locator_title', String()),
        Column('locator_href' , String()),
        Column('src'          , String()),
        Column('context'      , String()),
        Column('duration'     , Integer())
    ]
    # fmt: on
    assert len(res) == len(DbVisit._fields) + 1  # +1 because Locator is 'flattened'
    return res


def db_visit_to_row(v: DbVisit) -> tuple:
    # ugh, very hacky...
    # we want to make sure the resulting tuple only consists of simple types
    # so we can use dbengine directly
    dt_s = v.dt.isoformat()
    row = (
        v.norm_url,
        v.orig_url,
        dt_s,
        v.locator.title,
        v.locator.href,
        v.src,
        v.context,
        v.duration,
    )
    return row


def row_to_db_visit(row: Sequence) -> DbVisit:
    (norm_url, orig_url, dt_s, locator_title, locator_href, src, context, duration) = row
    dt_s = dt_s.split()[0]  # backwards compatibility: previously it could be a string separated with tz name
    dt = datetime.fromisoformat(dt_s)
    return DbVisit(
        norm_url=norm_url,
        orig_url=orig_url,
        dt=dt,
        locator=Loc(
            title=locator_title,
            href=locator_href,
        ),
        src=src,
        context=context,
        duration=duration,
    )
