from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
import sqlite3
from typing import List, Set

import pytz

from ..common import PathIsh, Results, Visit, Loc, get_logger, Second, mime
from .. import config

# todo mcachew?
from cachew import cachew

logger = get_logger()


def index(p: PathIsh) -> Results:
    pp = Path(p)
    assert pp.exists(), pp # just in case of broken symlinks

    # is_file check because it also returns dirs
    # TODO hmm, not sure what I meant here -- which dirs? behind symlinks?
    is_db = lambda x: x.is_file() and mime(x) in {
        'application/x-sqlite3',
        'application/vnd.sqlite3',
        # TODO this mime can also match wal files/journals, not sure
    }

    # todo warn if filtered out too many?
    # todo wonder how quickly mimes can be computed?
    # todo ugh, dunno, maybe this really belongs to hpi?? need get_files etc...
    dbs = [p for p in sorted(pp.rglob('*')) if is_db(p)]

    assert len(dbs) > 0, pp
    logger.info('processing %d databases', len(dbs))
    cname = str('_'.join(pp.parts[1:])) # meh
    yield from _index_dbs(dbs, cachew_name=cname)



def _index_dbs(dbs: List[Path], cachew_name: str):
    # TODO right... not ideal, need to think how to handle it properly...
    import sys
    sys.setrecursionlimit(5000)

    cache_dir = config.get().cache_dir
    cpath = None if cache_dir is None else cache_dir / cachew_name
    emitted: Set = set()
    yield from _index_dbs_aux(cpath, dbs, emitted=emitted)


# todo wow, stack traces are ridiculous here...
# todo hmm, feels like it should be a class or something?
@cachew(lambda cp, dbs, emitted: cp, depends_on=lambda cp, dbs, emitted: dbs) # , logger=logger)
def _index_dbs_aux(cache_path: Path, dbs: List[Path], emitted: Set) -> Results:
    if len(dbs) == 0:
        return

    xs = dbs[:-1]
    x  = dbs[-1:]

    xs_res = _index_dbs_aux(cache_path, xs, emitted)
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
    with sqlite3.connect(f'file:{db}?immutable=1', uri=True) as c:
        browser = None
        for b in [Chrome, Firefox, FirefoxPhone, Safari]:
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
            v = browser.row2visit(r, loc)
            total += 1

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
        url = unquote(url) # chrome urls are all quoted
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
    ts  = float(row['visit_date'])
    # ok, looks like it's unix epoch
    # https://stackoverflow.com/a/19430099/706389

    # NOTE: ugh. on Fenix (experimental Android version) it uses milliseconds, not nanos...
    # about year 2001... if someone has browser history exports before that -- please let me know, I'm impressed
    threshold = 1000000000
    if ts > threshold * 1_000_000:
        # presumably it's in microseconds
        ts /= 1_000_000
    else:
        # milliseconds
        ts /= 1_000
    dt = datetime.fromtimestamp(ts, pytz.utc)
    url = unquote(url) # firefox urls are all quoted
    return Visit(
        url=url,
        dt=dt,
        locator=loc,
    )

# https://web.archive.org/web/20201026130310/http://fileformats.archiveteam.org/wiki/History.db
class Safari(Extr):
    detector='history_tombstones'
    schema_check=(
        'history_visits', [
            'history_visits', "id, history_item, visit_time",
            'history_items', "id, url"
        ]
    )
    schema=Schema(cols=[
        ('U.url'                                  , 'TEXT'   ),

        # while these two are not very useful, might be good to have just in case for some debugging
        ('U.id AS urlid'                          , 'INTEGER'),
        ('V.id AS vid'                            , 'INTEGER'),

        ('V.visit_time'                           , 'INTEGER NOT NULL'),
        # ('V.from_visit'                           , 'INTEGER'         ),
        # ('V.transition'                           , 'INTEGER NOT NULL'),
        # V.segment_id looks useless
        # ('V.visit_duration'                       , 'INTEGER NOT NULL'),
        # V.omnibox thing looks useless
    ], key=('url', 'visit_time', 'vid', 'urlid'))
    query='FROM chunk.history_visits as V, chunk.history_items as U WHERE V.history_item = U.id'

    @staticmethod
    def row2visit(row: sqlite3.Row, loc: Loc) -> Visit:
        url  = row['url']
        ts   = row['visit_time'] + 978307200 # https://stackoverflow.com/a/34546556/16645
        dt = datetime.fromtimestamp(ts, pytz.utc)

        return Visit(
            url=url,
            dt=dt,
            locator=loc,
        )

# https://web.archive.org/web/20190730231715/https://www.forensicswiki.org/wiki/Mozilla_Firefox_3_History_File_Format#moz_historyvisits
class Firefox(Extr):
    detector='moz_meta'
    schema_check=('moz_historyvisits', "id, from_visit, place_id, visit_date, visit_type")
    schema=Schema(cols=[
        ('P.url'       , 'TEXT'),

        ('P.id AS pid' , 'INTEGER'),
        ('V.id AS vid' , 'INTEGER'),

        ('V.from_visit', 'INTEGER'),
        ('V.visit_date', 'INTEGER'),
        ('V.visit_type', 'INTEGER'),

        # not sure what session is form but could be useful?..
        # NOTE(20210410): for now, commented it out since some older databases from phone have this column commented?
        # needs to be defensive
        # ('V.session'   , 'INTEGER'),
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
