#!/usr/bin/env python3
import argparse
from datetime import datetime
import logging
import tempfile
from os.path import lexists
from typing import Optional, NamedTuple, Sequence, Tuple, Union
from pathlib import Path
import subprocess
from subprocess import check_call, DEVNULL, check_output

# pip3 install python-magic
import magic # type: ignore
mime = magic.Magic(mime=True)

from browser_history import Browser, backup_history, CHROME, FIREFOX, guess_db_date


def get_logger():
    return logging.getLogger('populate-browser-history')


def sqlite(db: Path, script, method=check_call, **kwargs):
    return method(['sqlite3', str(db), script], **kwargs)


def entries(db: Path) -> Optional[int]:
    if not db.exists():
        return None
    return int(sqlite(db, 'SELECT COUNT(*) FROM visits', method=check_output).decode('utf8'))


Col = Union[str, Tuple[str, Optional[str]]] # tuple is renaming
ColType = str


class Schema(NamedTuple):
    cols: Sequence[Tuple[Col, ColType]]
    key: Sequence[str]


SchemaCheck = Tuple[str, str]

def create(db: Path, table: str, schema: Schema):
    things = []
    for cc, tp in schema.cols:
        from_: str
        to: Optional[str]
        if isinstance(cc, str):
            from_ = cc
            to = cc
        else:
            (from_, to) = cc
        if to is not None:
            to = to.split('.')[-1] # strip off table alias
            to = to.split(' AS ')[-1]
            things.append(f'{to} {tp}')

    query = f"""
CREATE TABLE {table}(
    {', '.join(things)},
    PRIMARY KEY ({', '.join(schema.key)})
);
    """
    sqlite(db, query)


# at first, I was merging urls and visits tables separately... but it's kinda messy when you e.g. reinstall OS and table ids reset
# so joining before inserting makes a bit more sense.. we're throwing id anyway since it's fairly useless for the same reasons
# TODO it's a bit slow now because of the repeating joins presumably... could pass last handled visit date or something... not sure if it's safe
# TODO not sure how to make chunk read only?
def merge_browser(
        merged: Path,
        chunk: Path,
        schema: Schema,
        schema_check: SchemaCheck,
        query: str,
):
    check_table, expected = schema_check
    # ugh. a bit ugly but kinda works
    res = sqlite(chunk, f"select group_concat(name, ', ') from pragma_table_info('{check_table}')", method=check_output).decode('utf8').strip()
    if res != expected and not res in expected:
        raise AssertionError(f'expected schema {expected}, got {res}')
    # TODO default??


    if not merged.exists():
        create(merged, 'visits', schema)

    proj = ', '.join(c for c, _ in schema.cols) # type: ignore
    query = f"""
ATTACH '{chunk}' AS chunk;

INSERT OR IGNORE INTO main.visits
    SELECT {proj}
    {query};

DETACH chunk;
    """
    sqlite(merged, query)


class Extr(NamedTuple):
    detector: str
    schema_check: SchemaCheck
    schema: Schema
    query: str


chrome = Extr(
    detector='keyword_search_terms',
    schema_check=(
        'visits', [
            'visits', "id, url, visit_time, from_visit, transition, segment_id, visit_duration, incremented_omnibox_typed_score",
            'visits', "id, url, visit_time, from_visit, transition, segment_id, visit_duration",
        ]
    ),
    schema=Schema(cols=[
        ('U.url'                                  , 'TEXT'),

        # while these two are not very useful, might be good to have just in case for some debugging
        ('U.id AS urlid', 'INTEGER'),
        ('V.id AS vid', 'INTEGER'),

        ('V.visit_time'                             , 'INTEGER NOT NULL'),
        ('V.from_visit'                             , 'INTEGER'),
        ('V.transition'                             , 'INTEGER NOT NULL'),
        # V.segment_id looks useless
        ('V.visit_duration'                         , 'INTEGER NOT NULL'),
        # V.omnibox thing looks useless
    ], key=('url', 'visit_time', 'vid', 'urlid')),
    query='FROM chunk.visits as V, chunk.urls as U WHERE V.url = U.id',
)

# https://www.forensicswiki.org/wiki/Mozilla_Firefox_3_History_File_Format#moz_historyvisits
firefox = Extr(
    detector='moz_meta',
    schema_check=('moz_historyvisits', "id, from_visit, place_id, visit_date, visit_type, session"),
    schema=Schema(cols=[
        ('P.url'       , 'TEXT'),

        ('P.id AS pid' , 'INTEGER'),
        ('V.id AS vid' , 'INTEGER'),

        ('V.from_visit', 'INTEGER'),
        ('V.visit_date', 'INTEGER'),
        ('V.visit_type', 'INTEGER'),
        # not sure what session is form but could be useful?..
        ('V.session'   , 'INTEGER'),
    ], key=('url', 'visit_date', 'vid', 'pid')),
    query='FROM chunk.moz_historyvisits as V, chunk.moz_places as P WHERE V.place_id = P.id',
)


firefox_phone = Extr(
    detector='remote_devices',
    schema_check=('visits', "_id, history_guid, visit_type, date, is_local"),
    schema=Schema(cols=[
        ('H.url'         , 'TEXT NOT NULL'),

        ('H.guid AS guid', 'TEXT'),
        ('H._id  AS hid'  , 'INTEGER'),
        ('V._id  AS vid'  , 'INTEGER'),

        ('V.visit_type'  , 'INTEGER NOT NULL'),
        ('V.date'        , 'INTEGER NOT NULL'),
        # ('is_local'    , 'INTEGER NOT NULL'),
    ], key=('url', 'date', 'vid', 'hid')),
    query='FROM chunk.visits as V, chunk.history as H  WHERE V.history_guid = H.guid',
)

def merge(merged: Path, chunk: Path):
    logger = get_logger()
    logger.info(f"Merging {chunk} into {merged}")
    if lexists(merged):
        logger.info("DB size before: %s items %d bytes", entries(merged), merged.stat().st_size)
    else:
        logger.info(f"DB doesn't exist yet: {merged}")

    candidates = []
    for ff in [chrome, firefox, firefox_phone]:
        res = sqlite(chunk, f"SELECT * FROM {ff.detector}", method=subprocess.run, stdout=DEVNULL, stderr=DEVNULL)
        if res.returncode == 0:
            candidates.append(ff)
    assert len(candidates) == 1
    merger = candidates[0]

    merge_browser(merged=merged, chunk=chunk, schema=merger.schema, schema_check=merger.schema_check, query=merger.query)
    logger.info("DB size after : %s items %d bytes", entries(merged), merged.stat().st_size)


def merge_from(browser: Optional[Browser], from_: Optional[Path], to: Path, profile='*'):
    assert not to.is_dir()

    logger = get_logger()
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)

        if from_ is None:
            assert browser is not None
            backup_history(browser, tdir, profile=profile)
            from_ = tdir
        else:
            assert from_.exists()

        is_db = lambda x: x.is_file() and mime.from_file(str(x)) in ['application/x-sqlite3']

        if is_db(from_):
            files = [from_]
        else:
            files = sorted(x for x in from_.rglob('*') if is_db(x))

        for dbfile in files:
            # TODO maybe, assert they all of the same type?
            logger.info('merging %s', dbfile)
            merge(merged=to, chunk=dbfile)


def _helper(tmp_path, browser, profile='*'):
    logger = get_logger()

    tdir = Path(tmp_path)
    merged = tdir / 'merged.sqlite'

    entr = entries(merged)
    assert entr is None

    merge_from(browser, None, merged, profile=profile)
    merge_from(browser, None, merged, profile=profile)

    entr = entries(merged)
    assert entr is not None
    assert entr > 100 # quite arbitrary, but ok for now

def test_merge_chrome(tmp_path):
    _helper(tmp_path, CHROME)

def test_merge_firefox(tmp_path):
    _helper(tmp_path, FIREFOX, profile='*release')


def main():
    logger = get_logger()

    p = argparse.ArgumentParser()
    p.add_argument('--browser', type=Browser, required=False)
    p.add_argument('--to', type=Path, required=True)
    p.add_argument('--from', type=Path, default=None)
    p.add_argument('--profile', default='*')
    args = p.parse_args()

    from_ = getattr(args, 'from')

    # TODO need to mark already handled? although it's farily quick as it s
    # maybe should use the DB thing to handle merged??
    merge_from(browser=args.browser, from_=from_, to=args.to, profile=args.profile)


if __name__ == '__main__':
    main()


