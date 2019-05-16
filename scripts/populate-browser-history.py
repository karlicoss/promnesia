#!/usr/bin/env python3
import argparse
from datetime import datetime
import logging
import tempfile
from os.path import lexists
from typing import Optional, NamedTuple, Sequence, Tuple
from pathlib import Path
import subprocess
from subprocess import check_call, DEVNULL, check_output

# pip3 install python-magic
import magic # type: ignore
mime = magic.Magic(mime=True)

from kython.py37 import nullcontext
from kython.klogging import setup_logzero

from browser_history import Browser, backup_history, CHROME, FIREFOX, guess_db_date


def get_logger():
    return logging.getLogger('populate-browser-history')


def sqlite(db: Path, script, method=check_call, **kwargs):
    return method(['sqlite3', str(db), script], **kwargs)


def entries(db: Path) -> Optional[int]:
    if not db.exists():
        return None
    return int(sqlite(db, 'SELECT COUNT(*) FROM visits', method=check_output).decode('utf8')) # TODO


class Schema(NamedTuple):
    cols: Sequence[Tuple[str, str]]
    key: Sequence[str]


def create(db: Path, table: str, schema: Schema):
    xx = ', '.join(f'{col} {tp}' for col, tp in schema.cols)
    query = f"""
CREATE TABLE {table}(
    {xx},
    PRIMARY KEY ({', '.join(schema.key)})
);
    """
    sqlite(db, query)


# TODO it's a bit slow now because of the repeating joins presumably... could pass last handled visit date or something... not sure if it's safe
def merge_browser(
        merged: Path,
        chunk: Path,
        schema: Schema,
        query: str,
):
    # TODO chunk sould be read only?
    if not merged.exists():
        create(merged, 'visits', schema)

    sqlite(merged, f"""
ATTACH '{chunk}' AS chunk;

INSERT OR IGNORE INTO main.visits
    {query};

DETACH chunk;
    """)


class Extr(NamedTuple):
    detector: str
    schema: Schema
    query: str



chrome = Extr(
    detector='keyword_search_terms',
    schema=Schema(cols=[
        ('url'                            , 'TEXT'),

        # TODO SHIT! have to keep the order consistent, otherwise would end up with wrong data!
        # TODO I guess need to assert schema??? job for sqlalchemy?
        ('id'                             , 'INTEGER'),
        ('_url'                           , 'INTEGER NOT NULL'),
        ('visit_time'                     , 'INTEGER NOT NULL'),
        ('from_visit'                     , 'INTEGER'),
        ('transition'                     , 'INTEGER NOT NULL'),
        ('segment_id'                     , 'INTEGER'),
        ('visit_duration'                 , 'INTEGER NOT NULL'),
        ('incremented_omnibox_typed_score', 'BOOLEAN NOT NULL'),
    ], key=('url', 'visit_time')),
    query='SELECT U.url, V.* FROM chunk.visits as V, chunk.urls as U WHERE V.url = U.id',
)

# https://www.forensicswiki.org/wiki/Mozilla_Firefox_3_History_File_Format#moz_historyvisits
firefox = Extr(
    detector='moz_meta',
    schema=Schema(cols=[
        ('url'       , 'TEXT'),

        ('id'        , 'INTEGER'),
        ('from_visit', 'INTEGER'),
        ('place_id'  , 'INTEGER'),
        ('visit_date', 'INTEGER'),
        ('visit_type', 'INTEGER'),
        ('session'   , 'INTEGER'),
    ], key=('url', 'visit_date')),
    query='SELECT P.url, H.* FROM chunk.moz_historyvisits as H, chunk.moz_places as P WHERE H.place_id = P.id',
)
# TODO ok, visits are very important, whereas urls are no so much
# TODO not sure about visit id... maybe we don't really want them for easier merging? or primary key is pair of url and visit date instead?
# TODO uh. id is fairly useless anyway...
# TODO hmm. maybe not, since from_visit is quite useful.....
# TODO need to remove place id? not sure...


firefox_phone = Extr(
    detector='remote_devices',
    schema=Schema(cols=[
        ('url'         , 'TEXT NOT NULL'),

        ('_id'         , 'INTEGER NOT NULL'), # primary key in orig table, but here could be non unuque
        ('history_guid', 'TEXT NOT NULL'),
        ('visit_type'  , 'INTEGER NOT NULL'),
        ('date'        , 'INTEGER NOT NULL'),
        ('is_local'    , 'INTEGER NOT NULL'),
    ], key=('url', 'date')),
    query='SELECT H.url, V.* FROM chunk.history as H, chunk.visits as V WHERE H.guid = V.history_guid',
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

    merge_browser(merged=merged, chunk=chunk, schema=merger.schema, query=merger.query)
    logger.info("DB size after : %s items %d bytes", entries(merged), merged.stat().st_size)


def merge_from(browser: Optional[Browser], from_: Optional[Path], to: Path):
    assert not to.is_dir()

    logger = get_logger()
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)

        if from_ is None:
            assert browser is not None
            backup_history(browser, tdir)
            from_ = tdir

        for dbfile in sorted(x for x in from_.rglob('*') if x.is_file() and mime.from_file(str(x)) in ['application/x-sqlite3']):
            logger.info('merging %s', dbfile)
            merge(merged=to, chunk=dbfile)


def _helper(tmp_path, browser):
    logger = get_logger()
    setup_logzero(logger, level=logging.DEBUG)

    tdir = Path(tmp_path)
    merged = tdir / 'merged.sqlite'
    merge_from(browser, None, merged)
    merge_from(browser, None, merged)

    assert merged.stat().st_size > 10000 # TODO

def test_merge_chrome(tmp_path):
    _helper(tmp_path, CHROME)

def test_merge_firefox(tmp_path):
    _helper(tmp_path, FIREFOX)


def main():
    logger = get_logger()
    setup_logzero(logger, level=logging.DEBUG)

    p = argparse.ArgumentParser()
    p.add_argument('--browser', type=Browser, required=False)
    p.add_argument('--to', type=Path, required=True)
    p.add_argument('--from', type=Path, default=None)
    args = p.parse_args()

    from_ = getattr(args, 'from')

    # TODO need to mark already handled
    # although it's farily quick..
    # TODO hmm. maybe should use the DB thing to handle merged??
    merge_from(browser=args.browser, from_=from_, to=args.to)


if __name__ == '__main__':
    main()


