from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
import sqlite3
from typing import List

import pytz

from ..common import PathIsh, Results, Visit, Loc, get_logger


logger = get_logger()


def index(p: PathIsh) -> Results:
    pp = Path(p)
    # FIXME how to properly discover the databases? mime type maybe?
    dbs = list(sorted(pp.rglob('*.sqlite')))
    # here, we're assuming that inputs are immutable -- hence it's pointless to take the timestamp into the account?
    yield from _index_dbs(dbs)


def _index_dbs(dbs: List[Path]):
    for db in dbs:
        yield from _index_db(db)


# TODO hmm. cache could simply contain visits for each of the databases? and make it arbitrarily large
# although it's still annoying

def _index_db(db: Path):
    # TODO shit, it takes up quite a lot of memory, like 7 gigs for sikorsky merging
    logger.info('processing %s', db)
    from .populate import firefox as extr
    proj  = ', '.join(c for c, _ in extr.schema.cols)
    query = extr.query.replace('chunk.', '')

    # todo schema check (not so critical for cachew though)
    # TODO FIXME make sure it's reasonably defensive
    # db = dbs[1] # 656, 697
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
            # ok, looks like it's unix epoch
            # https://stackoverflow.com/a/19430099/706389
            dt = datetime.fromtimestamp(int(ts) / 1_000_000, pytz.utc)
            url = unquote(url) # firefox urls are all quoted
            yield Visit(
                url=url,
                dt=dt,
                locator=Loc.file(db), # fixme
            )

    # todo just yield visits directly? and cache them/make unique
    # I guess a downside is that time spent building visits, but it's only one time tradeoff


# TODO cache could simply override the default value?
# TODO ugh, dunno, maybe this really belongs to hpi?? need get_files etc...
