import logging
logger = logging.getLogger("WereYouHere")

from collections import OrderedDict
from datetime import datetime
from enum import Enum
from html.parser import HTMLParser
from os.path import join, lexists, isfile
from typing import List, Dict, Any, Optional
from urllib.parse import unquote
from zipfile import ZipFile
import json

from wereyouhere.common import Entry, History, Visit

# Mar 8, 2018, 5:14:40 PM
_TIME_FORMAT = "%b %d, %Y, %I:%M:%S %p"

class State(Enum):
    OUTSIDE = 0
    INSIDE = 1
    PARSING_LINK = 2
    PARSING_DATE = 3

# would be easier to use beautiful soup, but ends up in a big memory footprint..
class TakeoutHTMLParser(HTMLParser):
    state: State
    current: Dict[str, str]
    urls: History

    def __init__(self, tag: str) -> None:
        super().__init__()
        self.state = State.OUTSIDE
        self.urls = History()
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
                    time = datetime.strptime(times, _TIME_FORMAT)
                    visit = Visit(
                        dt=time,
                        tag=self.tag,
                    )
                    self.urls.register(url, visit)

                    self.current = {}
                    self.state = State.OUTSIDE
                    return

def _read_google_activity(myactivity_html_fo, tag: str):
    # # TODO ugh, for zip files we'd have to be more careful...
    # if not lexists(myactivity_html):
    #     logger.warning(f"{myactivity_html} is not present... skipping")
    #     return None

    data: str = myactivity_html_fo.read()
    parser = TakeoutHTMLParser(tag)
    parser.feed(data)
    return parser.urls

def _exists(thing, path):
    if isinstance(thing, ZipFile):
        # TODO
        raise NotImplementedError
    else:
        return lexists(join(thing, path))


def _open(thing, path):
    if isinstance(thing, ZipFile):
        return thing.open(path, 'r')
    else:
        return open(join(thing, path), 'r')


def read_google_activity(takeout) -> Optional[History]:
    spath = join("My Activity", "Chrome", "MyActivity.html")
    if not _exists(takeout, spath):
        logger.warning(f"{spath} is not present... skipping")
        return None
    with _open(takeout, spath) as fo:
        return _read_google_activity(fo, 'activity-chrome')

def read_search_activity(takeout) -> Optional[History]:
    spath = join("My Activity", "Search", "MyActivity.html")
    if not _exists(takeout, spath):
        logger.warning(f"{spath} is not present... skipping")
        return None
    with _open(takeout, spath) as fo:
        return _read_google_activity(fo, 'activity-search')

def read_browser_history_json(takeout) -> Optional[History]:
    spath = join("Chrome", "BrowserHistory.json")

    if not _exists(takeout, spath):
        logger.warning(f"{spath} is not present... skipping")
        return None

    j = None
    with _open(takeout, spath) as fo:
        j = json.load(fo)

    urls = History()
    hist = j['Browser History']
    for item in hist:
        url = item['url']
        time = datetime.fromtimestamp(item['time_usec'] / 10**6)
        visit = Visit(
            dt=time,
            tag="history_json",
        )
        urls.register(url, visit)
    return urls

def get_takeout_histories(takeout_path: str) -> List[History]:
    # first, figure out what is takeout_path...
    takeout = None
    if isfile(takeout_path):
        # must be a takeout zip
        # TODO support other formats too
        pass
    elif lexists(join(takeout_path, 'My Activity')):
        # unpacked dir, just process it
        takeout = takeout_path
    else:
        # TODO
        pass


    chrome_myactivity = read_google_activity(takeout_path)
    search_myactivity = read_search_activity(takeout_path)
    browser_history_json = read_browser_history_json(takeout_path)
    return [h for h in (
        chrome_myactivity,
        search_myactivity,
        browser_history_json,
        ) if h is not None]
