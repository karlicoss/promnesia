#!/usr/bin/env python3
"""
Run it occasionally to get a report of changes in your links database
"""
import json
import os
import os.path
from os.path import expanduser, dirname, lexists, join
import sys
from subprocess import check_call, check_output
import logging

STATE_DIR = expanduser("~/.cache/wereyouhere/")
STATE_FILE = join(STATE_DIR, 'state.json')
STATE_FILE_OLD = join(STATE_DIR, 'state.old.json')

# TODO use atomicwrite?

def get_logger():
    return logging.getLogger('wereyouhere-changes')


def load_state():
    if not lexists(STATE_FILE):
        return {}
    with open(STATE_FILE, 'r') as fo:
        return json.load(fo)

# although the database might inflate git repository due to everything in a single file, worth trying cause it makes everything way simpler..

def gits(*args, method=check_call):
    return method([
        'git', '-C', STATE_DIR, *args,
    ])

def init_state_dir():
    if not lexists(join(STATE_DIR, '.git')):
        os.makedirs(STATE_DIR, exist_ok=True)
        gits('init')

def save_state(new_state):
    total = sum(new_state.values())

    init_state_dir()
    with open(STATE_FILE, 'w') as fo:
        json.dump(new_state, fo, ensure_ascii=False, indent=1)
    gits('add', STATE_FILE)
    gits('commit', '--allow-empty', '-m', f'Update links db stats ({len(new_state)} urls with {total} total visits)')

    sz = check_output(['du', '-sh', STATE_DIR]).decode('utf-8').split()[0]
    print(f"Repository size: {sz}")

def print_diff():
    out = gits(
        'show',
        '--color',     # need to force it due to running non-interactively
        '-U0',         # do not show context
        '--word-diff', # do not use line changes, makes output more compact
        '-p',
        method=check_output,
    ).decode('utf-8').splitlines()
    out = [l for l in out if not '@@' in l]
    for l in out:
        print(l)

def load_urls():
    # TODO needs path to links db.... so it should use config?
    with open('/L/data/wereyouhere/linksdb.json', 'r') as fo:
        return json.load(fo)


def to_state(urls):
    """
    Essentially, simplifies the map so we can run comparisons accross different versions
    """
    stats = {url: len(vc[0]) + len(vc[1]) for url, vc in urls.items()}
    return stats

from compare_config import acceptable

diffs = []

def difference(rev, old, new):
    logger = get_logger()
    # os = to_state(old)
    # ns = to_state(new)
    os = old
    ns = new
    for url in sorted(set().union(os.keys(), ns.keys())):
        oc = os.get(url, 0)
        nc = ns.get(url, 0)
        if oc <= nc:
            continue # that's always good
        if acceptable(url=url, diff=oc - nc, rev=rev):
            continue
        diff = f'{url}: old {oc}, new {nc}'
        # print(diff) # TODO?
        diffs.append(diff)
        # if len(diffs) > 15:
        #     raise RuntimeError

def report_all():
    logger = get_logger()

    from kython.kgit import RepoHandle
    repo = RepoHandle('/L/Dropbox/tmp/wereyouhere')

    prev = None
    revisions = repo.revisions()
    # last = json.loads(repo.read_text(r[-1], 'state.json'))
    for r in revisions:
        logger.info('handing %r', r)
        cur = json.loads(repo.read_text(r, 'state.json'))
        if prev is None:
            logger.info('initial revision, no comparison!')
        else:
            difference(str(r), prev, cur)
        prev = cur


def main():
    logger = get_logger()
    from kython.klogging import setup_logzero
    setup_logzero(logger, level=logging.DEBUG)

    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--all', action='store_true')
    args = p.parse_args()
    if args.all:
        report_all()
    else:
        # TODO dry run so it doesn't save state? But then I wouldn't have diff (unless I print it beforehand)
        prev_state = load_state()
        new_state = to_state(load_urls())
        save_state(new_state)
        print_diff()


if __name__ == '__main__':
    main()
