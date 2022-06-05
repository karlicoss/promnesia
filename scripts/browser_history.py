#!/usr/bin/env python3
DEPRECATION = 'NOTE: this is DEPRECATED! Please use https://github.com/seanbreckenridge/browserexport instead'

from datetime import datetime
from pathlib import Path
from subprocess import check_output
import filecmp
import logging
import warnings
import sys

warnings.warn(DEPRECATION, DeprecationWarning)

Browser = str

CHROME = 'chrome'
FIREFOX = 'firefox'

def get_logger():
    return logging.getLogger('browser-history')


# TODO kython?
# TODO the with key?
def only(it):
    values = list(it)
    if len(values) == 1:
        return values[0]
    raise RuntimeError(f'Expected a single value: {values}')


def get_path(browser: Browser, profile: str='*') -> Path:
    if browser == 'chrome':
        bpath = Path('~/.config/google-chrome').expanduser()
        dbs = bpath.glob(profile + '/History')
    elif browser == 'firefox':
        bpath = Path('~/.mozilla/firefox/').expanduser()
        dbs = bpath.glob(profile + '/places.sqlite')
    else:
        raise RuntimeError(f'Unexpected browser {browser}')
    ldbs = list(dbs)
    if len(ldbs) == 1:
        return ldbs[0]
    raise RuntimeError(f'Expected single database, got {ldbs}. Perhaps you want to use --profile argument?')



def test_get_path():
    get_path('chrome')
    get_path('firefox', profile='*-release')


def atomic_copy(src: Path, dest: Path):
    """
    Supposed to handle cases where the file is changed while we were copying it.
    """
    import shutil

    differs = True
    while differs:
        res = shutil.copy(src, dest)
        differs = not filecmp.cmp(str(src), str(res))


def format_dt(dt: datetime) -> str:
    return dt.strftime('%Y%m%d%H%M%S')


def backup_history(browser: Browser, to: Path, profile: str='*', pattern=None) -> Path:
    assert to.is_dir()
    logger = get_logger()

    now = format_dt(datetime.utcnow())

    path = get_path(browser, profile=profile)

    pattern = path.stem + '-{}' + path.suffix if pattern is None else pattern
    fname = pattern.format(now)


    res = to / fname
    logger.info('backing up to %s', res)
    # if your chrome is open, database would normally be locked, so you can't just make a snapshot
    # so we'll just copy it till it converge. bit paranoid, but should work
    atomic_copy(path, res)
    logger.info('done!')
    return res


def test_backup_history(tmp_path):
    tdir = Path(tmp_path)
    backup_history(CHROME, tdir)
    backup_history(FIREFOX, tdir, profile='*-release')


def guess_db_date(db: Path) -> str:
    maxvisit = check_output([
        'sqlite3',
        '-csv',
        db,
        'SELECT max(datetime(((visits.visit_time/1000000)-11644473600), "unixepoch")) FROM visits;'
    ]).decode('utf8').strip().strip('"');
    return format_dt(datetime.strptime(maxvisit, "%Y-%m-%d %H:%M:%S"))


def test_guess(tmp_path):
    tdir = Path(tmp_path)
    db = backup_history(CHROME, tdir)
    guess_db_date(db)


def main():
    logger = get_logger()
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--browser', type=Browser, required=True)
    p.add_argument('--profile', type=str, default='*', help='Use to pick the correct profile to back up. If unspecified, will assume a single profile')
    p.add_argument('--to', type=Path, required=True)
    args = p.parse_args()

    # TODO do I need pattern??
    backup_history(browser=args.browser, to=args.to, profile=args.profile)

    warnings.warn(DEPRECATION, DeprecationWarning)
    logger.error("This script is DEPRECATED! Exiting with error code so that the use notices")
    sys.exit(44)


if __name__ == '__main__':
    main()
