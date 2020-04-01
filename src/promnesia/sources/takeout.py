import logging

import pytz
from collections import OrderedDict
import itertools
from datetime import datetime
from enum import Enum
from html.parser import HTMLParser
from os.path import join, lexists, isfile
import os
from typing import List, Dict, Any, Optional, Union, Iterable, Tuple
from urllib.parse import unquote # TODO mm, make it easier to rememember to use...
from zipfile import ZipFile
from pathlib import Path
import re
import json

from dateutil import parser

from ..common import PreVisit, get_logger, PathIsh, Url, Loc
from .. import config

from cachew import mtime_hash, cachew

# TODO reuse kython, but really, release takeout html parser separately

# TODO wonder if that old format used to be UTC...
# Mar 8, 2018, 5:14:40 PM
_TIME_FORMAT = "%b %d, %Y, %I:%M:%S %p %Z"

# ugh. something is seriously wrong with datetime, it wouldn't parse timezone aware UTC timestamp :(
def parse_dt(s: str) -> datetime:
    dt = parser.parse(s)
    if dt.tzinfo is None:
        # TODO log?
        # hopefully it was utc? Legacy, so no that much of an issue anymore..
        dt = dt.replace(tzinfo=pytz.utc)
    return dt

class State(Enum):
    OUTSIDE = 0
    INSIDE = 1
    PARSING_LINK = 2
    PARSING_DATE = 3

# would be easier to use beautiful soup, but ends up in a big memory footprint..
class TakeoutHTMLParser(HTMLParser):
    state: State
    current: Dict[str, str]
    visits: List[PreVisit]

    def __init__(self, *, kind: str, fpath: Path) -> None:
        super().__init__()
        self.state = State.OUTSIDE
        self.visits = []
        self.current = {}
        self.kind = kind
        self.locator = Loc.file(fpath)

    def _reg(self, name, value):
        assert name not in self.current
        self.current[name] = value

    def _astate(self, s): assert self.state == s

    def _trans(self, f, t):
        self._astate(f)
        self.state = t

    # enter content cell -> scan link -> scan date -> finish till next content cell
    def handle_starttag(self, tag: str, attrs) -> None:
        if self.state == State.INSIDE and tag == 'a':
            self.state = State.PARSING_LINK
            attrs = OrderedDict(attrs)
            hr = attrs['href']

            # sometimes it's starts with this prefix, it's apparently clicks from google search? or visits from chrome address line? who knows...
            # TODO handle http?
            prefix = r'https://www.google.com/url?q='
            if hr.startswith(prefix + "http"):
                hr = hr[len(prefix):]
                hr = unquote(hr)
            self._reg('url', hr)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'html':
            pass # ??

    def handle_data(self, data):
        if self.state == State.OUTSIDE:
            if data[:-1].strip() == "Visited":
                self.state = State.INSIDE
                return

        if self.state == State.PARSING_LINK:
            # self._reg(Entry.link, data)
            self.state = State.PARSING_DATE
            return

        if self.state == State.PARSING_DATE:
            # TODO regex?
            years = [str(i) + "," for i in range(2000, 2030)]
            for y in years:
                if y in data:
                    self._reg('time', data.strip())

                    url = self.current['url']
                    times = self.current['time']
                    time = parse_dt(times)
                    assert time.tzinfo is not None
                    visit = PreVisit(
                        url=url,
                        dt=time,
                        locator=self.locator,
                        debug=self.kind,
                    )
                    self.visits.append(visit)

                    self.current = {}
                    self.state = State.OUTSIDE
                    return


def _read_google_activity(myactivity_html_fo, *, kind: str, fpath: Path):
    # TODO is it possible to parse iteratively?
    data: str = myactivity_html_fo.read().decode('utf-8')
    parser = TakeoutHTMLParser(kind=kind, fpath=fpath)
    parser.feed(data)
    # TODO could be yieldy?? and use multiple processes?
    return parser.visits


TakeoutSource = Union[ZipFile, Path]

def _path(thing: TakeoutSource) -> Path:
    if isinstance(thing, Path):
        return thing
    else:
        return Path(thing.filename) # type: ignore

def _exists(thing: TakeoutSource, path):
    if isinstance(thing, ZipFile):
        return path in thing.namelist()
    else:
        return thing.joinpath(path).exists()


def _open(thing: TakeoutSource, path):
    if isinstance(thing, ZipFile):
        return thing.open(path, 'r')
    else:
        return thing.joinpath(path).open('rb')

def cacheme(ident: str):
    logger = get_logger()
    # doesn't even need a nontrivial hash function, timestsamp is encoded in name
    def db_pathf(takeout: TakeoutSource) -> Path:
        tpath = _path(takeout)
        cname = tpath.name + '_' + ident + '.cache'
        if config.has(): # TODO eh?
            cache_dir = Path(config.get().cache_dir)
        else:
            # TODO hmm. if using relative path, make it relative to /tmp?
            logger.warning('Caching in /tmp')
            cache_dir = Path('/tmp')
        return cache_dir / cname
    return cachew(db_pathf, cls=PreVisit, logger=logger)

@cacheme('google_activity')
def read_google_activity(takeout: TakeoutSource) -> List[PreVisit]:
    logger = get_logger()
    spath = join("Takeout", "My Activity", "Chrome", "MyActivity.html")
    if not _exists(takeout, spath):
        logger.warning(f"{spath} is not present in {takeout}... skipping")
        return []
    with _open(takeout, spath) as fo:
        return _read_google_activity(fo, kind='Chrome/MyAcvitity.html', fpath=_path(takeout))

@cacheme('search_activity')
def read_search_activity(takeout: TakeoutSource) -> List[PreVisit]:
    logger = get_logger()
    spath = join("Takeout", "My Activity", "Search", "MyActivity.html")
    if not _exists(takeout, spath):
        logger.warning(f"{spath} is not present in {takeout}... skipping")
        return []
    with _open(takeout, spath) as fo:
        return _read_google_activity(fo, kind='Search/MyActivity.html', fpath=_path(takeout))


# TODO add this to tests?
@cacheme('browser_activity')
def read_browser_history_json(takeout: TakeoutSource) -> Iterable[PreVisit]:
    logger = get_logger()
    spath = join("Takeout", "Chrome", "BrowserHistory.json")

    if not _exists(takeout, spath):
        logger.warning(f"{spath} is not present in {takeout}... skipping")
        return

    fpath = _path(takeout)
    locator = Loc.file(fpath)

    j = None
    with _open(takeout, spath) as fo: # TODO iterative parser?
        j = json.load(fo)

    hist = j['Browser History']
    for item in hist:
        url = item['url']
        time = datetime.utcfromtimestamp(item['time_usec'] / 10 ** 6).replace(tzinfo=pytz.utc)
        # TODO any more interesitng info?
        yield PreVisit(
            url=url,
            dt=time,
            locator=locator,
            debug='Chrome/BrowserHistory.json',
        )

_TAKEOUT_REGEX = re.compile(r'(\d{8}T\d{6}Z)')

def is_takeout_archive(fp: Path) -> bool:
    return fp.suffix == '.zip' and _TAKEOUT_REGEX.search(fp.stem) is not None

def takeout_candidates(takeouts_path: Path) -> Iterable[Path]:
    if not takeouts_path.exists():
        raise RuntimeError(f"{takeouts_path} doesn't exist!")

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
_Map = Dict[Key, PreVisit]

def _merge(current: _Map, new: Iterable[PreVisit]):
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
def extract(takeout_path_: PathIsh) -> Iterable[PreVisit]:
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
            tr = ZipFile(str(takeout))
        else:
            tr = takeout
        logger.info('handling takeout %s', tr)
        _merge(chrome_myactivity, read_google_activity(tr))
        _merge(search_myactivity, read_search_activity(tr))
        _merge(browser_history_json, read_browser_history_json(tr))
    return itertools.chain(chrome_myactivity.values(), search_myactivity.values(), browser_history_json.values())


index = extract # TODO deprecate 'extract'
