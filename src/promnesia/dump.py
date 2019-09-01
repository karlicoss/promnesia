from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import json
import shutil
import tempfile

from sqlalchemy import create_engine, MetaData # type: ignore
from sqlalchemy import Column, Table # type: ignore

from cachew import NTBinder, ichunks

from .common import get_logger, DbVisit
from .config import Config


def encoder(o):
    if isinstance(o, datetime):
        return o.isoformat() # hopefully that's ok; python 3.7 is capable of deserializing it, but I might have to backport it
    else:
        raise RuntimeError(f"can't encode {o}")

# jeez...
class hdict(dict):
    def __hash__(self):
        return hash(tuple(sorted(self.items())))

# shit, it's gonna be really hard to hack namedtuples int JSONEncoder...
# https://github.com/python/cpython/blob/dc078947a5033a048d804e244e847b5844734439/Lib/json/encoder.py#L263
# also guarantees consistent ordering...
def dictify(obj):
    if isinstance(obj, tuple) and hasattr(obj, '_asdict'):
        return dictify(obj._asdict()) # type: ignore
    elif isinstance(obj, dict):
        return hdict({k: dictify(v) for k, v in obj.items()})
    elif isinstance(obj, (list, tuple)):
        cls = type(obj)
        return cls(dictify(x) for x in obj)
    else:
        return obj


def dump_histories(all_histories: List[Tuple[str, List[DbVisit]]], config: Config):
    logger = get_logger()
    logger.info('preparing intermediate state...')

    output_dir = Path(config.OUTPUT_DIR)

    intm = output_dir / 'intermediate'
    intm.mkdir(exist_ok=True)

    # isoformat just to get away with comparing aware/unaware...
    cmp_key = lambda v: (v.norm_url, v.dt.isoformat(), v.context or '')
    # TODO not sure if here is a good place to normalise urls...
    intermediates = []
    for e, h in all_histories:
        cur = []
        for visit in sorted(h, key=cmp_key):
            dd = dictify(visit)
            dd['tag'] = dd['src']
            del dd['src'] # meh
            cur.append(dd)
        intermediates.append((e, cur))
    intp = intm.joinpath(datetime.utcnow().strftime('%Y%m%d%H%M%S.json'))
    with intp.open('w') as fo:
        json.dump(intermediates, fo, ensure_ascii=False, sort_keys=True, indent=1, default=encoder)
    logger.info('saved intermediate state to %s', intp)

    db_path = output_dir / 'promnesia.sqlite'

    def iter_visits():
        for e, h in all_histories:
            # TODO sort them somehow for determinism?
            # TODO what do we do with errors?
            # TODO maybe conform them to schema and dump too?
            # TODO or, dump to a separate table?
            yield from h

    ntf = tempfile.NamedTemporaryFile(delete=False)
    tpath = ntf.name
    engine = create_engine(f'sqlite:///{tpath}')
    binder = NTBinder.make(DbVisit)
    meta = MetaData(engine)
    table = Table('visits', meta, *binder.columns)
    meta.create_all()

    with engine.begin() as trans:
        for chunk in ichunks(iter_visits(), n=1000):
            bound = [binder.to_row(x) for x in chunk]
            # pylint: disable=no-value-for-parameter
            engine.execute(table.insert().values(bound))
    shutil.move(tpath, db_path)

    logger.info('saved database to %s', db_path)
