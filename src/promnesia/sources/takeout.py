import logging

import pytz
import itertools
from datetime import datetime
import os
from typing import List, Dict, Any, Optional, Union, Iterable, Tuple
from pathlib import Path
import re
import json

from my.kython.kompress import kexists, kopen

from ..common import Visit, get_logger, PathIsh, Url, Loc
from .. import config

from cachew import mtime_hash, cachew


# TODO use CPath? Could encapsulate a path within an archive *or* within a directory
TakeoutPath = Path


# TODO should this be HPI responsibility?
def cacheme(ident: str):
    logger = get_logger()
    # doesn't even need a nontrivial hash function, timestsamp is encoded in name
    def db_pathf(takeout: TakeoutPath) -> Path:
        tpath = Path(str(takeout))
        cname = tpath.name + '_' + ident + '.cache'
        if config.has(): # TODO eh?
            cache_dir = Path(config.get().cache_dir)
        else:
            # TODO hmm. if using relative path, make it relative to /tmp?
            logger.warning('Caching in /tmp')
            cache_dir = Path('/tmp')
        return cache_dir / cname
    return cachew(db_pathf, cls=Visit, logger=logger)


def _read_myactivity_html(takeout: TakeoutPath, kind: str) -> Iterable[Visit]:
    logger = get_logger()
    # TODO glob
    # TODO not sure about windows path separators??
    spath = 'Takeout/My Activity/' + kind
    if not kexists(takeout, spath):
        logger.warning(f"{spath} is not present in {takeout}... skipping")
        return []

    locator = Loc.file(spath)
    from my.google.takeout.html import read_html
    for dt, url, title in read_html(takeout, spath):
        yield Visit(
            url=url,
            dt=dt,
            locator=locator,
            debug=kind,
        )


@cacheme('google_activity')
def read_google_activity(takeout: TakeoutPath) -> Iterable[Visit]:
    return _read_myactivity_html(takeout, 'Chrome/MyActivity.html')

@cacheme('search_activity')
def read_search_activity(takeout: TakeoutPath) -> Iterable[Visit]:
    return _read_myactivity_html(takeout, 'Search/MyActivity.html')


# TODO add this to tests?
@cacheme('browser_activity')
def read_browser_history_json(takeout: TakeoutPath) -> Iterable[Visit]:
    # not sure if this deserves moving to HPI? it's pretty trivial for now
    logger = get_logger()
    spath = 'Takeout/Chrome/BrowserHistory.json'

    if not kexists(takeout, spath):
        logger.warning(f"{spath} is not present in {takeout}... skipping")
        return

    fpath = takeout
    locator = Loc.file(fpath)

    j = None
    with kopen(takeout, spath) as fo: # TODO iterative parser?
        j = json.load(fo)

    hist = j['Browser History']
    for item in hist:
        url = item['url']
        time = datetime.utcfromtimestamp(item['time_usec'] / 10 ** 6).replace(tzinfo=pytz.utc)
        # TODO any more interesitng info?
        yield Visit(
            url=url,
            dt=time,
            locator=locator,
            debug='Chrome/BrowserHistory.json',
        )


Key = Tuple[Url, datetime]
_Map = Dict[Key, Visit]

def _merge(current: _Map, new: Iterable[Visit]):
    logger = get_logger()
    # TODO would be nice to add specific takeout source??
    logger.debug('before merging: %d', len(current))
    for pv in new:
        key = (pv.url, pv.dt)
        if key in current:
            pass
        else:
            current[key] = pv
    logger.debug('after merging: %d', len(current))



# TODO make an iterator, insert in db as we go? handle errors gracefully?
def index() -> Iterable[Visit]:
    logger = get_logger()

    from my.google.takeout.paths import get_takeouts
    takeouts = get_takeouts()

    browser_history_json: _Map = {}
    chrome_myactivity: _Map = {}
    search_myactivity: _Map = {}

    # TODO we need to use CPath here? Also CPath should support kopen, kexists?
    # TODO anyway, need to support unpacked takeouts..
    for takeout in takeouts:
        logger.info('handling takeout %s', takeout)
        # TODO use more_itertools for merging
        _merge(chrome_myactivity, read_google_activity(takeout))
        _merge(search_myactivity, read_search_activity(takeout))
        _merge(browser_history_json, read_browser_history_json(takeout))
    return itertools.chain(
        chrome_myactivity.values(),
        search_myactivity.values(),
        browser_history_json.values(),
    )
