#!/usr/bin/env python3

from datetime import datetime
import os
from os.path import expanduser

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

def backup_to(prefix: str):
    today = datetime.now().strftime("%Y%m%d")
    BPATH = f"{prefix}/{today}/"

    os.makedirs(BPATH, exist_ok=True)

    DB = expanduser("~/.config/google-chrome/Default/History")

    # TODO do we need journal?
    # ~/.config/google-chrome/Default/History-journal

    # if your chrome is open, database would normally be locked, so you can't just make a snapshot
    # so we'll just copy it till it converge. bit paranoid, but should work
    atomic_copy(DB, BPATH)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Backup tool for chrome history db")
    parser.add_argument('backup-prefix', type=str, help="Base folder for chrome DB backups. Should generally be same as CHROME_HISTORY_DB_DIR in config.py")
    args = parser.parse_args()
    prefix = getattr(args, 'backup-prefix')
    backup_to(prefix)

if __name__ == '__main__':
    main()
