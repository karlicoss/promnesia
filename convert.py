from datetime import datetime
from typing import NamedTuple
from pathlib import Path

# TODO binder thing needs to be extracted?
from kython.kcache import Binder
from kython.py37 import fromisoformat


# TODO intermediate repr can be guarded by mypy
class Visit(NamedTuple):
    url: str
    dt: datetime
    context: str
    tag: str
    # TODO locator?


p = Path('/L/data/wereyouhere/intermediate/20190509090714.json')


import ijson # type: ignore
import json

items = []

import pytz

def alala_visit(v):
    url = v['url']
    # TODO parse loc
    for vis in v['visits']:
        dt = fromisoformat(vis['dt'])
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
            # TODO FIXME
            # dt = config.FALLBACK_TIMEZONE.localize(dt)

        ld = vis['locator']
        # loc = Loc(file=ld['file'], line=ld['line'])

        yield Visit(
            url=url,
            dt=dt,
            # locator=loc,
            context=vis['context'],
            tag=vis['tag'],
        )

from itertools import islice

LIMIT = None

def iter_json():
    with p.open('r') as fo:
        ints = islice(ijson.items(fo, 'item'), 0, LIMIT)
        for src, src_visits in ints:
            for v in src_visits:
                yield from alala_visit(v)

from sqlalchemy import create_engine, MetaData # type: ignore
from sqlalchemy import Column, Table # type: ignore

# TODO ???

db_path = Path('visits.sqlite')
db = create_engine(f'sqlite:///{db_path}')
engine = db.connect()
meta = MetaData(engine)
binder = Binder(clazz=Visit)
table = Table('visits', meta, *binder.columns)
meta.create_all()


from kython import ichunks
with engine.begin() as transaction:
    engine.execute(table.delete())
    for chunk in ichunks(iter_json(), n=1000):
        bound = [tuple(binder.to_row(x)) for x in chunk]
        engine.execute(table.insert().values(bound))


