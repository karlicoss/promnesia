from ..common import Visit, logger, PathIsh, Url, Loc, Results

# TODO make an iterator, insert in db as we go? handle errors gracefully?
def index() -> Results:
    from . import hpi
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



import pytz
from itertools import chain
from datetime import datetime
from typing import List, Optional, Iterable, TYPE_CHECKING
from pathlib import Path
import json


from .. import config


from more_itertools import unique_everseen
from cachew import cachew


# TODO use CPath? Could encapsulate a path within an archive *or* within a directory
TakeoutPath = Path


def _read_myactivity_html(takeout: TakeoutPath, kind: str) -> Iterable[Visit]:
    from my.core.kompress import kexists
    # TODO glob
    # TODO not sure about windows path separators??
    spath = 'Takeout/My Activity/' + kind
    if not kexists(takeout, spath):
        logger.warning(f"{spath} is not present in {takeout}... skipping")
        return
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

def _cpath(suffix: str):
    def fun(takeout: TakeoutPath):
        cache_dir = config.get().cache_dir
        if cache_dir is None:
            return None
        # doesn't need a nontrivial hash function, timestsamp is encoded in name
        return cache_dir / (takeout.name + '_' + suffix + '.cache')
    return fun


# todo caching should this be HPI responsibility?
# todo set global cachew logging on init?
@cachew(cache_path=_cpath('google_activity') , logger=logger)
def read_google_activity(takeout: TakeoutPath) -> Iterable[Visit]:
    return _read_myactivity_html(takeout, 'Chrome/MyActivity.html')

@cachew(cache_path=_cpath('search_activity') , logger=logger)
def read_search_activity(takeout: TakeoutPath) -> Iterable[Visit]:
    return _read_myactivity_html(takeout, 'Search/MyActivity.html')

# TODO add this to tests?
@cachew(cache_path=_cpath('browser_activity'), logger=logger)
def read_browser_history_json(takeout: TakeoutPath) -> Iterable[Visit]:
    from my.core.kompress import kexists, kopen
    # not sure if this deserves moving to HPI? it's pretty trivial for now
    spath = 'Takeout/Chrome/BrowserHistory.json'

    if not kexists(takeout, spath):
        logger.warning(f"{spath} is not present in {takeout}... skipping")
        return
    logger.info('processing %s %s', takeout, spath)

    # TODO couls also add spath?
    locator = Loc.file(takeout)

    # TODO this should be supported by HPI now?

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

