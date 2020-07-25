from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
import sqlite3
from typing import List, Set

import pytz

from ..common import PathIsh, Results, Visit, Loc, get_logger, Second


logger = get_logger()


def index(p: PathIsh, glob='*.sqlite') -> Results:
    pp = Path(p)
    # TODO how to properly discover the databases? mime type maybe?
    # TODO ugh, dunno, maybe this really belongs to hpi?? need get_files etc...
    assert pp.exists() # just in case of broken symlinks
    dbs = list(sorted(pp.rglob(glob)))
    assert len(dbs) > 0, pp
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


# todo wow, stack traces are ridiculous here...
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
            # hmm ok it might happen if we messed up with indexing individual db?
            # alternatively, could abuse it to avoid messing with 'emitted' in _index_db?
            emitted.add(key)
        yield r # todo not sure about exceptions?

    for db in x:
        yield from _index_db(db, emitted=emitted)


def _index_db(db: Path, emitted: Set):
    logger.info('processing %s', db) # debug level?

    # todo schema check (not so critical for cachew though)
    total = 0
    new   = 0
    loc = Loc.file(db) # todo possibly needs to be optimized -- moving from within the loop considerably speeds everything up
    with sqlite3.connect(db) as c: # TODO iterate over all of them..
        browser = None
        for b in [Chrome, Firefox, FirefoxPhone]:
            try:
                c.execute(f'SELECT * FROM {b.detector}')
            except sqlite3.OperationalError: # not sure if the right kind?
                pass
            else:
                browser = b
                break
        assert browser is not None

        proj  = ', '.join(c for c, _ in browser.schema.cols)
        query = browser.query.replace('chunk.', '')

        c.row_factory = sqlite3.Row
        for r in c.execute(f'select {proj} {query}'):
            # TODO column names should probably be mapped straightaway...
            # although it's tricky, need to handle timestamps etc properly?
            # alternatively, could convert datetimes as sqlite functions?
            # eh. not worth it. e.g. quoting etc

            v = browser.row2visit(r, loc)
            total += 1

            # TODO hmm, bring this optimization back.. 37 secs?
            key = (v.url, v.dt)
            # todo how to keep keys compatible?
            if key in emitted:
                continue
            yield v
            emitted.add(key)
            new += 1

            # eh, ok, almost 2x faster if I don't construct Visit first
            # maybe it's Loc.file that's too slow?
            # yeah, seems like it, 4.1 s after computing it only once

    logger.info('%s: %d/%d new visits', db, new, total)


# TODO limit cachew version??


Col = str
ColType = str


from typing import Any, NamedTuple, Tuple, Union, Sequence, Optional

class Schema(NamedTuple):
    cols: Sequence[Tuple[Col, ColType]]
    key: Sequence[str]


SchemaCheck = Tuple[str, Union[str, Sequence[str]]] # todo Union: meh

from dataclasses import dataclass

# todo protocol?
@dataclass
class Extr:
    detector: str
    schema_check: SchemaCheck
    schema: Schema
    query: str

    # todo calllable?
    @staticmethod
    def row2visit(row: sqlite3.Row, loc: Loc) -> Visit:
        raise NotImplementedError


class Chrome(Extr):
    detector='keyword_search_terms'
    schema_check=(
        'visits', [
            'visits', "id, url, visit_time, from_visit, transition, segment_id, visit_duration, incremented_omnibox_typed_score",
            'visits', "id, url, visit_time, from_visit, transition, segment_id, visit_duration"
        ]
    )
    schema=Schema(cols=[
        ('U.url'                                  , 'TEXT'   ),

        # while these two are not very useful, might be good to have just in case for some debugging
        ('U.id AS urlid'                          , 'INTEGER'),
        ('V.id AS vid'                            , 'INTEGER'),

        ('V.visit_time'                           , 'INTEGER NOT NULL'),
        ('V.from_visit'                           , 'INTEGER'         ),
        ('V.transition'                           , 'INTEGER NOT NULL'),
        # V.segment_id looks useless
        ('V.visit_duration'                       , 'INTEGER NOT NULL'),
        # V.omnibox thing looks useless
    ], key=('url', 'visit_time', 'vid', 'urlid'))
    query='FROM chunk.visits as V, chunk.urls as U WHERE V.url = U.id'

    @staticmethod
    def row2visit(row: sqlite3.Row, loc: Loc) -> Visit:
        url  = row['url']
        ts   = row['visit_time']
        durs = row['visit_duration']

        dt = chrome_time_to_utc(int(ts))
        url = unquote(url) # chrome urls are all quoted # TODO not sure if we want it here?
        dd = int(durs)
        dur: Optional[Second] = None if dd == 0 else dd // 1_000_000
        return Visit(
            url=url,
            dt=dt,
            locator=loc,
            duration=dur,
        )


# should be utc? https://stackoverflow.com/a/26226771/706389
# yep, tested it and looks like utc
def chrome_time_to_utc(chrome_time: int) -> datetime:
    epoch = (chrome_time / 1_000_000) - 11644473600
    return datetime.fromtimestamp(epoch, pytz.utc)


def _row2visit_firefox(row: sqlite3.Row, loc: Loc) -> Visit:
    url = row['url']
    ts  = row['visit_date']
    # ok, looks like it's unix epoch
    # https://stackoverflow.com/a/19430099/706389
    dt = datetime.fromtimestamp(int(ts) / 1_000_000, pytz.utc)
    url = unquote(url) # firefox urls are all quoted
    return Visit(
        url=url,
        dt=dt,
        locator=loc,
    )


# https://www.forensicswiki.org/wiki/Mozilla_Firefox_3_History_File_Format#moz_historyvisits
class Firefox(Extr):
    detector='moz_meta'
    schema_check=('moz_historyvisits', "id, from_visit, place_id, visit_date, visit_type, session")
    schema=Schema(cols=[
        ('P.url'       , 'TEXT'),

        ('P.id AS pid' , 'INTEGER'),
        ('V.id AS vid' , 'INTEGER'),

        ('V.from_visit', 'INTEGER'),
        ('V.visit_date', 'INTEGER'),
        ('V.visit_type', 'INTEGER'),
        # not sure what session is form but could be useful?..
        ('V.session'   , 'INTEGER'),
    ], key=('url', 'visit_date', 'vid', 'pid'))
    query='FROM chunk.moz_historyvisits as V, chunk.moz_places as P WHERE V.place_id = P.id'

    row2visit = _row2visit_firefox


class FirefoxPhone(Extr):
    detector='remote_devices'
    schema_check=('visits', "_id, history_guid, visit_type, date, is_local")
    schema=Schema(cols=[
        ('H.url'               , 'TEXT NOT NULL'   ),

        ('H.guid AS guid'      , 'TEXT'            ),
        ('H._id  AS hid'       , 'INTEGER'         ),
        ('V._id  AS vid'       , 'INTEGER'         ),

        ('V.visit_type'        , 'INTEGER NOT NULL'),
        ('V.date as visit_date', 'INTEGER NOT NULL'),
        # ('is_local'    , 'INTEGER NOT NULL'),
    ], key=('url', 'date', 'vid', 'hid'))
    query='FROM chunk.visits as V, chunk.history as H  WHERE V.history_guid = H.guid'

    row2visit = _row2visit_firefox
