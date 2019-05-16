#!/usr/bin/env python3
import argparse
from datetime import datetime
import logging
import tempfile
from os.path import lexists
from typing import Optional
from pathlib import Path
from subprocess import check_call, DEVNULL

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

def create(db: Path, table: str, columns):
    xx = ', '.join(f'{col} {tp}' for col, tp in columns)
    query = f"""
CREATE TABLE {table}(
    {xx}
);
    """
    sqlite(db, query)

def merge_firefox(merged: Path, chunk: Path):
    # TODO sanity check
    # TODO read only?
    sqlite(chunk, "SELECT * FROM moz_meta", stdout=DEVNULL)
    visits = [
        # TODO not sure about primary key here..
        ('url'       , 'TEXT'),

        ('visit_date', 'INTEGER'),
        ('id'        , 'INTEGER PRIMARY KEY'),
        ('from_visit', 'INTEGER'),
        ('place_id'  , 'INTEGER'),
        ('visit_type', 'INTEGER'),
        ('session'   , 'INTEGER'),
    ]
    # TODO shit. title might change... not really sure I should keep it...
    if not merged.exists():
        create(merged, 'visits', visits)
    # TODO ok, visits are very important, whereas urls are no so much
    # TODO not sure about visit id... maybe we don't really want them for easier merging? or primary key is pair of url and visit date instead?
    # TODO uh. id is fairly useless anyway...
    # TODO hmm. maybe not, since from_visit is quite useful.....
    sqlite(merged, f"""
ATTACH '{chunk}' AS chunk;

INSERT OR IGNORE INTO main.visits
    SELECT P.url, H.* FROM chunk.moz_historyvisits as H, chunk.moz_places as P WHERE H.place_id = P.id;

DETACH chunk;
    """)
# TODO need to remove place id? not sure...

def merge(browser: Browser, merged: Path, chunk: Path):
    logger = get_logger()
    # TODO script relative to path
    logger.info(f"Merging {chunk} into {merged}")
    if lexists(merged):
        logger.info(f"Merged DB size before: {merged.stat().st_size}")
    else:
        logger.info(f"Merged DB doesn't exist yet: {merged}")
    if browser == FIREFOX:
        merge_firefox(merged=merged, chunk=chunk)
    else:
        MERGE_SCRIPT = Path(__file__).parent.absolute() / f'merge-db/merge-{browser}.sh'
        check_call([MERGE_SCRIPT, str(merged), str(chunk)])
    logger.info(f"Merged DB size after: {merged.stat().st_size}")


def merge_from(browser: Browser, from_: Optional[Path], to: Path):
    assert not to.is_dir()

    logger = get_logger()
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)

        if from_ is None:
            backup_history(browser, tdir)
            from_ = tdir

        for dbfile in sorted(x for x in from_.rglob('*') if x.is_file() and mime.from_file(str(x)) in ['application/x-sqlite3']):
            logger.info('merging %s', dbfile)
            merge(browser=browser, merged=to, chunk=dbfile)

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
    p.add_argument('--browser', type=Browser, required=True)
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


