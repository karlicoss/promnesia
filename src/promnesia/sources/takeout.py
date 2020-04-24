# TODO should probably move this whole thing to HPI
import logging

import pytz
from collections import OrderedDict
import itertools
from datetime import datetime
import os
from typing import List, Dict, Any, Optional, Union, Iterable, Tuple
from urllib.parse import unquote # TODO mm, make it easier to rememember to use...
from pathlib import Path
import re
import json

from my.kython.kompress import kexists, kopen
from my.kython.ktakeout import parse_dt

from ..common import Visit, get_logger, PathIsh, Url, Loc
from .. import config

from cachew import mtime_hash, cachew


TakeoutSource = Path

# TODO this should be HPI responsibility?
def cacheme(ident: str):
    logger = get_logger()
    # doesn't even need a nontrivial hash function, timestsamp is encoded in name
    def db_pathf(takeout: TakeoutSource) -> Path:
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


# TODO Cpath?
def _read_myactivity(takeout: TakeoutSource, kind: str) -> Iterable[Visit]:
    logger = get_logger()
    # TODO glob
    # TODO not sure about windows path separators??
    spath = 'Takeout/My Activity/' + kind
    if not kexists(takeout, spath):
        logger.warning(f"{spath} is not present in {takeout}... skipping")
        return []

    locator = Loc.file(spath)
    from my.takeout import read_html
    for dt, url, title in read_html(takeout, spath):
        yield Visit(
            url=url,
            dt=dt,
            locator=locator,
            debug=kind,
        )


@cacheme('google_activity')
def read_google_activity(takeout: TakeoutSource) -> Iterable[Visit]:
    return _read_myactivity(takeout, 'Chrome/MyActivity.html')

@cacheme('search_activity')
def read_search_activity(takeout: TakeoutSource) -> Iterable[Visit]:
    return _read_myactivity(takeout, 'Search/MyActivity.html')


# TODO add this to tests?
@cacheme('browser_activity')
def read_browser_history_json(takeout: TakeoutSource) -> Iterable[Visit]:
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

_TAKEOUT_REGEX = re.compile(r'(\d{8}T\d{6}Z)')

def is_takeout_archive(fp: Path) -> bool:
    return fp.suffix == '.zip' and _TAKEOUT_REGEX.search(fp.stem) is not None

# TODO move this to hpi?
def takeout_candidates(takeouts_path: Path) -> Iterable[Path]:
    if not takeouts_path.exists():
        raise RuntimeError(f"{takeouts_path} doesn't exist!")

    # TODO def use my.takeout for it
    if takeouts_path.is_file():
        if is_takeout_archive(takeouts_path):
            yield takeouts_path
    for root, dirs, files in os.walk(str(takeouts_path)): # TODO make sure it traverses inside in case it's a symlink
        rp = Path(root)
        if rp.joinpath('Takeout').exists():
            # TODO hmm, maybe src should be assigned to non-frozen dataclasses??
            yield rp

        for f in files:
            fp = Path(root, f)
            if fp.suffix == '.zip' and _TAKEOUT_REGEX.search(fp.stem):
                # TODO support other formats too
                # TODO multipart archives?
                yield fp

Key = Tuple[Url, datetime]
_Map = Dict[Key, Visit]

def _merge(current: _Map, new: Iterable[Visit]):
    logger = get_logger()
    # TODO would be nice to add specific takeout source??
    logger.debug('before merging %s: %d', 'TODO', len(current))
    for pv in new:
        key = (pv.url, pv.dt)
        if key in current:
            pass
            # logger.debug('skipping %s', pv)
        else:
            # logger.info('adding %s', pv)
            current[key] = pv
    logger.debug('after merging %s: %d', 'TODO', len(current))



# TODO make an iterator, insert in db as we go? handle errors gracefully?
def index(takeout_path_: PathIsh) -> Iterable[Visit]:
    logger = get_logger()
    path = Path(takeout_path_)

    takeouts = []
    for t in takeout_candidates(path):
        if t.is_dir():
            # TODO uh, not a great way I guess
            dts = datetime.utcfromtimestamp(t.stat().st_mtime).strftime('%Y%m%dT%H%M%SZ')
            takeouts.append((dts, t))
        else: # must be an archive
            dts = _TAKEOUT_REGEX.search(t.stem).group(1) # type: ignore
            takeouts.append((dts, t))

    browser_history_json: _Map = {}
    chrome_myactivity: _Map = {}
    search_myactivity: _Map = {}

    for dts, takeout in sorted(takeouts):
        tr: TakeoutSource
        if not takeout.is_dir(): # must be zip file
            # TODO Cpath?
            tr = takeout
        else:
            tr = takeout
        logger.info('handling takeout %s', tr)
        _merge(chrome_myactivity, read_google_activity(tr))
        _merge(search_myactivity, read_search_activity(tr))
        _merge(browser_history_json, read_browser_history_json(tr))
    return itertools.chain(chrome_myactivity.values(), search_myactivity.values(), browser_history_json.values())


extract = index # TODO deprecate 'extract'
