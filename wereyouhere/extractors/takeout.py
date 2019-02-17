import logging

import pytz
from collections import OrderedDict
import itertools
from datetime import datetime
from enum import Enum
from html.parser import HTMLParser
from os.path import join, lexists, isfile
import os
from typing import List, Dict, Any, Optional, Union, Iterable
from urllib.parse import unquote
from zipfile import ZipFile
from pathlib import Path
import re
import json

from dateutil import parser

from wereyouhere.common import PreVisit, get_logger, PathIsh, Tag


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

    def __init__(self, tag: str) -> None:
        super().__init__()
        self.state = State.OUTSIDE
        self.visits = []
        self.current = {}
        self.tag = tag

    def _reg(self, name, value):
        assert name not in self.current
        self.current[name] = value

    def _astate(self, s): assert self.state == s

    def _trans(self, f, t):
        self._astate(f)
        self.state = t

    # enter content cell -> scan link -> scan date -> finish till next content cell
    def handle_starttag(self, tag, attrs):
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

    def handle_endtag(self, tag):
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
                        tag=self.tag,
                    )
                    self.visits.append(visit)

                    self.current = {}
                    self.state = State.OUTSIDE
                    return

def _read_google_activity(myactivity_html_fo, tag: str):
    # TODO is it possible to parse iteratively?
    data: str = myactivity_html_fo.read().decode('utf-8')
    parser = TakeoutHTMLParser(tag)
    parser.feed(data)
    return parser.visits

def _exists(thing, path):
    if isinstance(thing, ZipFile):
        return path in thing.namelist()
    else:
        return thing.joinpath(path).exists()


def _open(thing, path):
    if isinstance(thing, ZipFile):
        return thing.open(path, 'r')
    else:
        return thing.joinpath(path).open('rb')

def read_google_activity(takeout) -> List[PreVisit]:
    logger = get_logger()
    spath = join("Takeout", "My Activity", "Chrome", "MyActivity.html")
    if not _exists(takeout, spath):
        logger.warning(f"{spath} is not present... skipping")
        return []
    with _open(takeout, spath) as fo:
        return _read_google_activity(fo, 'activity-chrome')

def read_search_activity(takeout) -> List[PreVisit]:
    logger = get_logger()
    spath = join("Takeout", "My Activity", "Search", "MyActivity.html")
    if not _exists(takeout, spath):
        logger.warning(f"{spath} is not present... skipping")
        return []
    with _open(takeout, spath) as fo:
        return _read_google_activity(fo, 'activity-search')

# TODO add this to tests?
def read_browser_history_json(takeout) -> Iterable[PreVisit]:
    logger = get_logger()
    spath = join("Takeout", "Chrome", "BrowserHistory.json")

    if not _exists(takeout, spath):
        logger.warning(f"{spath} is not present... skipping")
        return []

    j = None
    with _open(takeout, spath) as fo:
        j = json.load(fo)

    hist = j['Browser History']
    for item in hist:
        url = item['url']
        time = datetime.utcfromtimestamp(item['time_usec'] / 10 ** 6).replace(tzinfo=pytz.utc)
        # TODO any more interesitng info?
        yield PreVisit(
            url=url,
            dt=time,
            tag="history_json",
        )

def extract(takeout_path_: PathIsh, tag: Tag) -> Iterable[PreVisit]:
    path = Path(takeout_path_)

    # first, figure out what is takeout_path...
    takeout: Union[ZipFile, Path]
    if path.is_file():
        # must be a takeout zip
        # TODO support other formats too
        takeout = ZipFile(str(path))
    elif path.joinpath('Takeout', 'My Activity').exists():
        # unpacked dir, just process it
        takeout = path
    else:
        # directory with multiple takeout archives
        TAKEOUT_REGEX = re.compile(r'takeout-\d{8}T\d{6}Z')
        takeout_name = max([ff for ff in path.iterdir() if TAKEOUT_REGEX.match(ff.name)]) # lastest chronologically
        takeout = ZipFile(str(path.joinpath(takeout_name)))
        # TODO multipart archives?
    chrome_myactivity = read_google_activity(takeout)
    search_myactivity = read_search_activity(takeout)
    browser_history_json = read_browser_history_json(takeout)
    return itertools.chain(chrome_myactivity, search_myactivity, browser_history_json)
