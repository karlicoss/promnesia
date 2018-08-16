#!/usr/bin/env python3

from datetime import datetime
import logging
import os
from os.path import expanduser, join, getsize, lexists
from os import listdir
import shutil
from tempfile import TemporaryDirectory
from typing import Optional


def get_logger():
    return logging.getLogger("WereYouHere")


def atomic_copy(src: str, dest: str):
    """
    Supposed to handle cases where the file is changed while we were copying it.
    """
    import shutil
    import filecmp

    differs = True
    while differs:
        res = shutil.copy(src, dest)
        differs = not filecmp.cmp(src, res)

def backup_to(prefix: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    BPATH = f"{prefix}/{today}/"

    os.makedirs(BPATH, exist_ok=True)

    DB = expanduser("~/.config/google-chrome/Default/History")

    # TODO do we need journal?
    # ~/.config/google-chrome/Default/History-journal

    # if your chrome is open, database would normally be locked, so you can't just make a snapshot
    # so we'll just copy it till it converge. bit paranoid, but should work
    atomic_copy(DB, BPATH)
    return join(BPATH, "History")

def merge(merged: str, chunk: str):
    logger = get_logger()
    from subprocess import check_call
    # TODO script relative to path
    logger.info(f"Merging {chunk} into {merged}")
    if lexists(merged):
        logger.info(f"Merged DB size before: {getsize(merged)}")
    else:
        logger.info(f"Merged DB doesn't exist yet: {merged}")
    check_call(['/L/coding/were-you-here/scripts/merge-chrome-db/merge.sh', merged, chunk])
    logger.info(f"Merged DB size after: {getsize(merged)}")

def merge_all_from(merged: str, merge_from: str, move_to: str):
    for d in sorted(listdir(merge_from)):
        hdb = join(merge_from, d, 'History')
        if lexists(hdb): # TODO sqlite mime?
            merge(merged, hdb)
            if move_to is not None:
                shutil.move(join(merge_from, d), move_to)
            else:
                os.unlink(hdb)
                os.rmdir(join(merge_from, d))
                # could use shutil.rmtree, but don't want to remove extra files by accident...

def main():
    logging.basicConfig(level=logging.INFO)

    import argparse
    parser = argparse.ArgumentParser(description="Backup and merge tool for chrome history db")
    parser.add_argument('--backup', action='store_true', default=False)
    parser.add_argument('--backup-to', type=str, default=None)
    parser.add_argument('--merge', action='store_true', default=False)
    parser.add_argument('--merge-from', type=str, default=None)
    parser.add_argument('--merge-to', type=str, default=None, help="Database containing merged visits. Used as input to CHROME_HISTORY_DB in config.py")
    parser.add_argument('--move-to', type=str, default=None, help="Where to move merged chunks (empty if you want to trash them, merge-to/merged by default)")
    args = parser.parse_args()

    if args.backup ^ (args.merge_from is None):
        raise RuntimeError("One and only one of --backup and --merge-from makes no sense!")

    tdir: Optional[TemporaryDirectory] = None
    merge_from: str

    if args.backup:
        tdir = TemporaryDirectory()
        bdir = args.backup_to if args.backup_to is not None else tdir.name
        backup_to(bdir)
        merge_from = bdir
    else:
        merge_from = args.merge_from

    if args.merge: # TODO merge should always be set??
        assert args.merge_to is not None
        move_to: Optional[str]
        if args.move_to is None:
            move_to = join(merge_from, 'merged')
            if not lexists(move_to):
                os.makedirs(move_to)
        elif args.move_to == "":
            move_to = None
        else:
            move_to = args.move_to
        merge_all_from(args.merge_to, merge_from, move_to)

    if tdir is not None:
        tdir.cleanup()

if __name__ == '__main__':
    main()
