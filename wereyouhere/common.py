from collections.abc import Sized
from datetime import datetime, date
import re
from typing import NamedTuple, Set, Iterable, Dict, TypeVar, Callable, List, Optional, Union, Any, Collection
from pathlib import Path
import logging
from functools import lru_cache

import pytz

from .normalise import normalise_url


from kython.ktyping import PathIsh


from typing_extensions import Protocol


Url = str
Tag = str
DatetimeIsh = Union[datetime, date, str]
Context = str

# TODO hmm. arguably, source and context are almost same things...
# locator? source then context within file
class Loc(NamedTuple):
    file: str
    line: Optional[int]=None

    @classmethod
    def make(cls, fname: PathIsh, **kwargs):
        return cls(file=str(fname), **kwargs)

    # TODO need some uniform way of string conversion
    # but generally, it would be
    # (url|file)(linenumber|json_path|anchor)

class PreVisit(NamedTuple):
    url: Url
    dt: DatetimeIsh
    locator: Loc
    context: Optional[Context] = None
    tag: Optional[Tag] = None

Extraction = Union[PreVisit, Exception]


class Visit(NamedTuple):
    dt: datetime
    locator: Loc
    tag: Optional[Tag] = None
    context: Optional[Context] = None

    def __hash__(self):
        # well, that's quite mad. but dict is not hashable..
        # pylint: disable=no-member
        ll = self._replace(locator=None) # type: ignore
        # pylint: disable=bad-super-call
        return super(Visit, ll).__hash__()

    @property
    def cmp_key(self):
        return (self.dt, str(self.tag), str(self.context))
    # TODO deserialize method??

# TODO should ve even split url off Visit? not sure what benefit that actually gives..
class Entry(NamedTuple):
    url: Url
    visits: Set[Visit]
    # TODO compare urls?

Filter = Callable[[Url], bool]

def make_filter(thing) -> Filter:
    if isinstance(thing, str):
        rc = re.compile(thing)
        def filter_(u: str) -> bool:
            return rc.search(u) is not None
        return filter_
    else: # must be predicate
        return thing

# TODO do i really need to inherit this??
class History(Sized):
    FILTERS: List[Filter] = [
        make_filter(f) for f in
        [
            r'^chrome-devtools://',
            r'^chrome-extension://',
            r'^chrome-error://',
            r'^chrome-native://',
            r'^chrome-search://',

            r'chrome://newtab',
            r'chrome://apps',
            r'chrome://history',

            r'^about:',
            r'^blob:',
            r'^view-source:',

            r'^content:',

            # TODO maybe file:// too?
            # chrome-search:
        ]
    ]

    @classmethod
    def add_filter(cls, filterish):
        cls.FILTERS.append(make_filter(filterish))

    def __init__(self):
        self.urls: Dict[Url, Entry] = {}

    @classmethod
    def from_urls(cls, urls: Dict[Url, Entry], filters: List[Filter] = None) -> 'History':
        hist = cls()
        hist.urls = urls
        return hist

    # TODO mm. maybe history should get filters from some global config?
    # wonder how okay is it to set class attribute..

    @classmethod
    def filtered(cls, url: Url) -> bool:
        for f in cls.FILTERS:
            if f(url):
                return True
        return False

    def register(self, url: Url, v: Visit) -> None:
        if History.filtered(url):
            return
        if v.dt.tzinfo is None:
            # TODO log that?...
            pass
        # TODO replace dt i

        # TODO hmm some filters make sense before stripping off protocol...
        # TODO is it a good place to normalise?
        url = normalise_url(url)

        e = self.urls.get(url, None)
        if e is None:
            e = Entry(url=url, visits=set())
        e.visits.add(v)
        self.urls[url] = e

    def __contains__(self, k) -> bool:
        return k in self.urls

    def __len__(self) -> int:
        return len(self.urls)

    def __getitem__(self, url: Url) -> Entry:
        return self.urls[url]

    def items(self):
        return self.urls.items()

    def __repr__(self):
        return 'History{' + repr(self.urls) + '}'

# f is value merger function
_K = TypeVar("_K")
_V = TypeVar("_V")

def merge_dicts(f: Callable[[_V, _V], _V], dicts: Iterable[Dict[_K, _V]]):
    res: Dict[_K, _V] = {}
    for d in dicts:
        for k, v in d.items():
            if k not in res:
                res[k] = v
            else:
                res[k] = f(res[k], v)
    return res

def entry_merger(a: Entry, b: Entry):
    a.visits.update(b.visits)
    return a

def merge_histories(hists: Iterable[History]) -> History:
    return History.from_urls(merge_dicts(entry_merger, [h.urls for h in hists]))

def get_logger():
    return logging.getLogger("WereYouHere")


# kinda singleton
@lru_cache()
def get_tmpdir():
    import tempfile
    tdir = tempfile.TemporaryDirectory(suffix="wereyouhere")
    return tdir

@lru_cache()
def _get_extractor():
    from urlextract import URLExtract # type: ignore
    u = URLExtract()
    # https://github.com/lipoja/URLExtract/issues/13
    # u._stop_chars_right |= {','}
    # u._stop_chars_left  |= {','}
    return u


def sanitize(url: str) -> str:
    # TODO not sure it's a really good idea.. but seems easiest now
    # TODO have whitelisted urls that allow trailing parens??
    url = url.strip(',.…\\')
    if 'wikipedia' not in url:
        # urls might end with parens en.wikipedia.org/wiki/Widget_(beer)
        url = url.strip(')')
    return url


def extract_urls(s: str) -> List[str]:
    # TODO unit test for escaped urls.. or should it be in normalise instead?
    if len(s.strip()) == 0:
        return [] # optimize just in case..

    # TODO special handling for org links

    # TODO fuck. doesn't look like it's handling multiple urls in same line well...
    # ("python.org/one.html python.org/two.html",
    # hopefully ok... I guess if there are spaces in url we are fucked anyway..
    extractor = _get_extractor()
    urls: List[str] = []
    for x in s.split():
        urls.extend(extractor.find_urls(x))

    return [sanitize(u) for u in urls]


def from_epoch(ts: int) -> datetime:
    res = datetime.utcfromtimestamp(ts)
    res.replace(tzinfo=pytz.utc)
    return res


# TODO kythonize?
class PathWithMtime(NamedTuple):
    path: Path
    mtime: float

    @classmethod
    def make(cls, p: Path):
        return cls(
            path=p,
            mtime=p.stat().st_mtime,
        )


class Config(Protocol):
    FALLBACK_TIMEZONE: pytz.BaseTzInfo
    OUTPUT_DIR: PathIsh
    EXTRACTORS: List
    FILTERS: List[str]



def import_config(config_file: PathIsh) -> Config:
    mpath = Path(config_file)
    import os, sys, importlib
    sys.path.append(mpath.parent.as_posix())
    try:
        res = importlib.import_module(mpath.stem)
        # TODO hmm. check that config conforms to the protocol?? perhaps even in config itself?
        return res # type: ignore
    finally:
        sys.path.pop()

