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
    _DBS = dbs[:1000] # TODO FIXME
    yield from _index_dbs(_DBS)

# 8.65s user
# 3.83s user


# todo perhaps I need some profiling?


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

_CACHED = 10


# todo cachew this?
# todo not sure if it should cache results or raw browser data instead?
def some_cached_visits() -> Results:
    # from . import demo
    # yield from demo.index(100)
    emitted: Set = set()
    for db in _DBS[:_CACHED]:
        yield from _index_db(db, emitted, marker='C')


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
    if len(xs) == _CACHED:
        xs_iter = some_cached_visits()
    else:
        xs_iter = _index_dbs_2(xs, emitted=emitted)
    ####
    was_cached = False
    for r in xs_iter:
        # if at this point emitted is empty, we'd have to populate it
        # todo this is extra work, can be determined by the first emission??
        if len(emitted) == 0:
            # if it wasn't cached, emitted would be populated
            was_cached = True
        if was_cached:
            # need to
            key = (r.url, r.dt) # todo orig??
            if key in emitted:
                # hmm, this shouldn't be the case?
                # alternatively, could abuse it to avoid messing with 'emitted' in _index_db?
                continue
            emitted.add(key)
        yield r # todo not sure about exceptions?

    # then, populate it? But need to keep all emitted in memory? ugh.
    # TODO might take too much stack??
    for db in x:
        # TODO process, handle emitted
        yield from _index_db(db, emitted=emitted)

# TODO hmm. cache could simply contain visits for each of the databases? and make it arbitrarily large
# although it's still annoying
# nah, gonna be ridiculous duplication

def _index_db(db: Path, emitted: Set, marker='xx'):
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
    loc = Loc.file(db) # ??
    with sqlite3.connect(db) as c: # TODO iterate over all of them..
        c.row_factory = sqlite3.Row
        for r in c.execute(f'select {proj} {query}'):
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
            # TODO compare performance? not sure if it would matter much with caching
            # i.e. without caching it's shit either way
            # key = (url, ts)
            # if key in emitted:
            #     continue
            # emitted.add(key)
            # new += 1

            # ok, looks like it's unix epoch
            # https://stackoverflow.com/a/19430099/706389
            dt = datetime.fromtimestamp(int(ts) / 1_000_000, pytz.utc)
            url = unquote(url) # firefox urls are all quoted

            # eh, ok, almost 2x faster if I don't construct Visit first
            # maybe it's Loc.file that's too slow?
            # yeah, seems like it, 4.1 s after computing it only once
            key = (url, dt)
            if key in emitted:
                continue

            v = Visit(
                url=url,
                dt=dt,
                locator=loc,
            )
            yield v
            # logger.info(marker) # todo get rid of it
            emitted.add(key)
            new += 1

            # ok, this is def better
            # todo how to keep keys compatible?

    logger.info('%s: %d/%d new visits', db, new, total)

    # todo just yield visits directly? and cache them/make unique
    # I guess a downside is that time spent building visits, but it's only one time tradeoff


# TODO cache could simply override the default value?
# TODO ugh, dunno, maybe this really belongs to hpi?? need get_files etc...
