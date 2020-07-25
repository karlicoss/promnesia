from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
import sqlite3
from typing import List, Set

import pytz

from ..common import PathIsh, Results, Visit, Loc, get_logger


logger = get_logger()


def index(p: PathIsh) -> Results:
    pp = Path(p)
    # TODO how to properly discover the databases? mime type maybe?
    # TODO ugh, dunno, maybe this really belongs to hpi?? need get_files etc...
    dbs = list(sorted(pp.rglob('*.sqlite')))
    # here, we're assuming that inputs are immutable -- hence it's pointless to take the timestamp into the account?
    dbs = dbs[:11] # TODO FIXME
    yield from _index_dbs(dbs)


def _index_dbs(dbs: List[Path]):
    # TODO right... not ideal, need to think how to handle it properly...
    import sys
    sys.setrecursionlimit(2000)

    emitted: Set = set()
    # for db in dbs:
    yield from _index_dbs_aux(dbs, emitted=emitted)


# todo mcachew?
from cachew import cachew
from cachew.experimental import enable_exceptions
enable_exceptions()


# todo filename  should probably include the source names or something?
@cachew(hashf=lambda dbs, emitted: dbs)
def _index_dbs_aux(dbs: List[Path], emitted: Set) -> Results:
    if len(dbs) == 0:
        return

    xs = dbs[:-1]
    x  = dbs[-1:]

    xs_res = _index_dbs_aux(xs, emitted=emitted)
    xs_was_cached = False
    for r in xs_res:
        # if it was cached, emitted would be empty
        if len(emitted) == 0:
            xs_was_cached = True
            logger.debug('seems that %d first items were previously cached', len(xs))
        if xs_was_cached:
            key = (r.url, r.dt)
            assert key not in emitted, key # todo not sure if this assert is necessary?
            # alternatively, could abuse it to avoid messing with 'emitted' in _index_db?
            emitted.add(key)
        yield r # todo not sure about exceptions?

    for db in x:
        yield from _index_db(db, emitted=emitted)


def _index_db(db: Path, emitted: Set):
    logger.info('processing %s', db) # debug level?
    from .populate import firefox as extr
    proj  = ', '.join(c for c, _ in extr.schema.cols)
    query = extr.query.replace('chunk.', '')

    # todo schema check (not so critical for cachew though)
    total = 0
    new   = 0
    loc = Loc.file(db) # todo possibly needs to be optimized -- moving from within the loop considerably speeds everything up
    with sqlite3.connect(db) as c: # TODO iterate over all of them..
        c.row_factory = sqlite3.Row
        for r in c.execute(f'select {proj} {query}'):
            # TODO column names should probably be mapped straightaway...
            # although it's tricky, need to handle timestamps etc properly?
            # alternatively, could convert datetimes as sqlite functions?
            # eh. not worth it. e.g. quoting etc

            url = r['url']
            ts  = r['visit_date']

            total += 1

            # ok, looks like it's unix epoch
            # https://stackoverflow.com/a/19430099/706389
            dt = datetime.fromtimestamp(int(ts) / 1_000_000, pytz.utc)
            url = unquote(url) # firefox urls are all quoted

            # eh, ok, almost 2x faster if I don't construct Visit first
            # maybe it's Loc.file that's too slow?
            # yeah, seems like it, 4.1 s after computing it only once
            key = (url, dt)
            # todo how to keep keys compatible?
            if key in emitted:
                continue

            v = Visit(
                url=url,
                dt=dt,
                locator=loc,
            )
            yield v
            emitted.add(key)
            new += 1

    logger.info('%s: %d/%d new visits', db, new, total)


# TODO limit cachew version??
