from collections import OrderedDict
from enum import Enum
from html.parser import HTMLParser
from os.path import join
from typing import List, Dict, Any

from wereyouhere.common import Entry, History

class State(Enum):
    OUTSIDE = 0
    INSIDE = 1
    PARSING_LINK = 2
    PARSING_DATE = 3

class TakeoutHTMLParser(HTMLParser):
    state: State
    current: Dict[str, Any]
    urls: History

    def __init__(self):
        super().__init__()
        self.state = State.OUTSIDE
        self.urls = {}
        self.current = {}

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
            self._reg('url', hr)
            return

    def handle_endtag(self, tag):
        if tag == 'html':
            pass # ??

    def handle_data(self, data):
        if self.state == State.OUTSIDE:
            if data[:-1] == "Visited":
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
                    self._reg('time', data)
                    # coll = from_pdict(Entry, self.current)

                    url = self.current['url']
                    time = self.current['time']
                    e = self.urls.get(url, None)
                    if e is None:
                        e = Entry(url=url, visits=set())
                    e.visits.add(time)
                    self.urls[url] = e

                    self.current = {}
                    self.state = State.OUTSIDE
                    return

def read_google_activity(takeout_dir: str) -> History:
    myactivity_html = join(takeout_dir, "My Activity", "Chrome", "MyActivity.html")

    data: str
    with open(myactivity_html, 'r') as fo:
        data = fo.read()
    parser = TakeoutHTMLParser()
    parser.feed(data)
    return parser.urls

def get_takeout_histories(takeout_dir: str) -> List[History]:
    chrome_myactivity = read_google_activity(takeout_dir)
    return [chrome_myactivity]
