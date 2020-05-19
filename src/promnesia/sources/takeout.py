'''
Uses HPI [[https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#mygoogletakeoutpaths][google.takeout]] module
'''

import logging

import pytz
from itertools import chain
from datetime import datetime
from typing import List, Optional, Iterable
from pathlib import Path
import json

from my.kython.kompress import kexists, kopen

from ..common import Visit, get_logger, PathIsh, Url, Loc, Results
from .. import config


from more_itertools import unique_everseen
from cachew import mtime_hash, cachew


# TODO use CPath? Could encapsulate a path within an archive *or* within a directory
TakeoutPath = Path


# TODO should this be HPI responsibility?
# TODO FIXME belongs to cachew?
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
    logger.info('processing %s %s', takeout, kind)

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
    logger.info('processing %s %s', takeout, spath)

    # TODO couls also add spath?
    locator = Loc.file(takeout)

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


# TODO make an iterator, insert in db as we go? handle errors gracefully?
def index() -> Results:
    from my.google.takeout.paths import get_takeouts
    takeouts = list(get_takeouts())
    # TODO if no takeouts, raise?
    # although could raise a warning on top level, when source emitted no takeouts

    # TODO youtube?
    google_activities = [read_google_activity(t)      for t in takeouts]
    search_activities = [read_search_activity(t)      for t in takeouts]
    browser_histories = [read_browser_history_json(t) for t in takeouts]

    key = lambda v: (v.dt, v.url)
    return chain(
        unique_everseen(chain(*google_activities), key=key),
        unique_everseen(chain(*search_activities), key=key),
        unique_everseen(chain(*browser_histories), key=key),
    )
