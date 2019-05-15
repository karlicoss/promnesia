#!/usr/bin/env python3
import argparse
from datetime import datetime
import logging
import tempfile
from os.path import lexists
from typing import Optional
from pathlib import Path
from subprocess import check_call

# pip3 install python-magic
import magic # type: ignore
mime = magic.Magic(mime=True)

from kython.py37 import nullcontext
from kython.klogging import setup_logzero

from browser_history import Browser, backup_history, CHROME, FIREFOX, guess_db_date


def get_logger():
    return logging.getLogger('populate-browser-history')

_MERGE_SCRIPT = Path(__file__).parent.absolute() / 'merge-chrome-db/merge.sh'

def merge(merged: Path, chunk: Path):
    logger = get_logger()
    # TODO script relative to path
    logger.info(f"Merging {chunk} into {merged}")
    if lexists(merged):
        logger.info(f"Merged DB size before: {merged.stat().st_size}")
    else:
        logger.info(f"Merged DB doesn't exist yet: {merged}")
    check_call([_MERGE_SCRIPT, str(merged), str(chunk)])
    logger.info(f"Merged DB size after: {merged.stat().st_size}")


def merge_from(browser: Browser, from_: Optional[Path], to: Path):
    assert not to.is_dir()
    assert browser == CHROME # TODO support firefox

    logger = get_logger()
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)

        if from_ is None:
            backup_history(browser, tdir)
            from_ = tdir

        for dbfile in sorted(x for x in from_.rglob('*') if mime.from_file(str(x)) in ['application/x-sqlite3']):
            logger.info('merging %s', dbfile)
            merge(merged=to, chunk=dbfile)


def test_merge_from(tmp_path):
    logger = get_logger()
    setup_logzero(logger, level=logging.DEBUG)

    tdir = Path(tmp_path)
    merged = tdir / 'merged.sqlite'
    merge_from(CHROME, None, merged)
    merge_from(CHROME, None, merged)

    assert merged.stat().st_size > 10000 # TODO


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


