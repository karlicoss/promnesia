from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
import sqlite3
from typing import List, Set

import pytz

from ..common import PathIsh, Results, Visit, Loc, get_logger


logger = get_logger()


_DBS = None # todo remove

def index(p: PathIsh) -> Results:
    pp = Path(p)
    # FIXME how to properly discover the databases? mime type maybe?
    dbs = list(sorted(pp.rglob('*.sqlite')))
    # here, we're assuming that inputs are immutable -- hence it's pointless to take the timestamp into the account?
    global _DBS
    _DBS = dbs[:10] # TODO FIXME
    yield from _index_dbs(_DBS)


def _index_dbs(dbs: List[Path]):
    emitted: Set = set()
    # for db in dbs:
    yield from _index_dbs_2(dbs, emitted=emitted)


# TODO ok, have some simple schema for it?
#
from typing import Iterable, NamedTuple


# before,   it's called index([db1, db2]     , emitted=<set1>). Result is cached
# now , we call it with index([db1, db2, db3], emitted=<set2>).
#                       index([db1, db2]) returns the results, and doesn't touch emitted


from cachew import cachew

# right, so it throws 'database is locked' immediately...

CACHED = 5


# todo cachew this?
def some_cached_visits() -> Results:
    # from . import demo
    # yield from demo.index(100)
    emitted: Set = set()
    for db in _DBS[:CACHED]:
        yield from _index_db(db, emitted)


from typing import Optional
#
# @cachew
def _index_dbs_2(dbs: List[Path], emitted: Set) -> Results:
    if len(dbs) == 0:
        return

    xs = dbs[:-1]
    x  = dbs[-1:]
    print(len(xs), len(x))
    #### this will be hidden from us! we won't know which alternative is true
    if len(xs) == CACHED:
        xs_iter = some_cached_visits()
    else:
        xs_iter = _index_dbs_2(xs, emitted=emitted)
    ####
    for r in xs_iter:
        # if at this point emitted is empty, we'd have to populate it
        yield r # todo not sure about exceptions?
        # todo this is extra work, can be determined by the first emission??
        key = (r.url, r.dt) # todo orig??
        if key in emitted:
            continue
        emitted.add(key)
    # TODO FIXME keys are inconsistent..

    # yield from _index_dbs_2(xs, emitted=emitted)
    # todo if emitted is None, means all of them were cached?
    # then, populate it? But need to keep all emitted in memory? ugh.
    # TODO might take too much stack??
    for db in x:
        # TODO process, handle emitted
        yield from _index_db(db, emitted=emitted)

# TODO hmm. cache could simply contain visits for each of the databases? and make it arbitrarily large
# although it's still annoying
# nah, gonna be ridiculous duplication

def _index_db(db: Path, emitted: Set):
    # TODO shit, it takes up quite a lot of memory, like 7 gigs for phone merging
    # for kammerer, also a lot of time to reindex from scratch. it's also not CPU bound? odd.
    logger.info('processing %s', db)
    from .populate import firefox as extr
    proj  = ', '.join(c for c, _ in extr.schema.cols)
    query = extr.query.replace('chunk.', '')

    # todo schema check (not so critical for cachew though)
    # TODO FIXME make sure it's reasonably defensive
    # db = dbs[1] # 656, 697
    total = 0
    new   = 0
    with sqlite3.connect(db) as c: # TODO iterate over all of them..
        c.row_factory = sqlite3.Row
        for r in c.execute(f'select {proj} {query}'):
            # print(r['url'], r['visit_date'])
    # TODO column names should probably be mapped straightaway...
    # although it's tricky, need to handle timestamps etc properly?
    # alternatively, could convert datetimes as sqlite functions?
    # eh. not worth it. e.g. quoting etc
    #
            url = r['url']
            ts  = r['visit_date']

            total += 1
            # yeah, _way_ better this way. seems it would be essential
            # there is also vid/hid/urlid etc, but not sure if we care about them?..
            key = (url, ts)
            if key in emitted:
                continue
            emitted.add(key)
            new += 1

            # ok, looks like it's unix epoch
            # https://stackoverflow.com/a/19430099/706389
            dt = datetime.fromtimestamp(int(ts) / 1_000_000, pytz.utc)
            url = unquote(url) # firefox urls are all quoted
            yield Visit(
                url=url,
                dt=dt,
                locator=Loc.file(db), # fixme
            )
    logger.info('%s: %d/%d new visits', db, new, total)

    # todo just yield visits directly? and cache them/make unique
    # I guess a downside is that time spent building visits, but it's only one time tradeoff


# TODO cache could simply override the default value?
# TODO ugh, dunno, maybe this really belongs to hpi?? need get_files etc...
