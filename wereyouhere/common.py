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
from kython.kerror import Res, unwrap

import dateparser # type: ignore
from typing_extensions import Protocol


Url = str
Tag = str
DatetimeIsh = Union[datetime, date, str]
Context = str
Second = int

# TODO hmm. arguably, source and context are almost same things...
# locator? source then context within file
class Loc(NamedTuple):
    # file: str
    # line: Optional[int]=None
    title: str
    href: Optional[str]=None

    # @classmethod
    # def file(cls, fname: PathIsh, **kwargs):
    #     return cls(file=str(fname), **kwargs)

    @classmethod
    def make(cls, title, href=None):
        return cls(title=title, href=href)

    @classmethod
    def file(cls, path: PathIsh, line: Optional[int]=None):
        ll = '' if line is None else f':{line}'
        loc = f'{path}{ll}'
        return cls.make(
            title=loc,
            href=f'emacs:{loc}'
        )

    # TODO need some uniform way of string conversion
    # but generally, it would be
    # (url|file)(linenumber|json_path|anchor)


# TODO serialize unions? Might be a bit mad...
# TODO FIXME need to discard cache...
class PreVisit(NamedTuple):
    url: Url
    dt: datetime # TODO FIXME back to DatetimeIsh, but somehow make compatible to dbcache
    locator: Loc
    context: Optional[Context] = None
    tag: Optional[Tag] = None
    # TODO shit. I need to insert it in chrome db....
    # TODO gonna be hard to fill retroactively.
    # spent: Optional[Second] = None


Extraction = Union[PreVisit, Exception]

class DbVisit(NamedTuple):
    norm_url: Url
    orig_url: Url
    dt: datetime
    locator: Loc
    tag: Optional[Tag] = None
    context: Optional[Context] = None

    @staticmethod
    def make(p: PreVisit) -> Res['DbVisit']:
        try:
            if isinstance(p.dt, str):
                dt = dateparser.parse(p.dt)
            elif isinstance(p.dt, datetime):
                dt = p.dt
            elif isinstance(p.dt, date):
                dt = datetime.combine(p.dt, datetime.min.time()) # meh..
            else:
                raise AssertionError(f'unexpected date: {p.dt}, {type(p.dt)}')
        except Exception as e:
            return e

        try:
            nurl = normalise_url(p.url)
        except Exception as e:
            return e

        return DbVisit(
            # TODO shit, can't handle errors properly here...
            norm_url=nurl,
            orig_url=p.url,
            dt=dt,
            locator=p.locator,
            tag=p.tag,
            context=p.context,
        )


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
        self.vmap: Dict[PreVisit, DbVisit] = {}

    # TODO mm. maybe history should get filters from some global config?
    # wonder how okay is it to set class attribute..

    @classmethod
    def filtered(cls, url: Url) -> bool:
        for f in cls.FILTERS:
            if f(url):
                return True
        return False

    @property
    def visits(self):
        return self.vmap.values()

    def register(self, v: PreVisit) -> Optional[Exception]:
        # TODO should we filter before normalising? not sure...
        if History.filtered(v.url):
            return None

        if v in self.vmap:
            return None

        try:
            # TODO if we do it as unwrap(DbVisit.make, v), then we can access make return type and properly handle error type?
            db_visit = unwrap(DbVisit.make(v))
        except Exception as e:
            return e

        self.vmap[v] = db_visit
        return None
        # TODO hmm some filters make sense before stripping off protocol...

    # only used in tests?..
    def _nmap(self):
        from kython import group_by_key
        return group_by_key(self.visits, key=lambda x: x.norm_url)

    def __len__(self) -> int:
        return len(self._nmap())

    def __contains__(self, url) -> bool:
        return url in self._nmap()

    def __getitem__(self, url: Url):
        return self._nmap()[url]

    def __repr__(self):
        return 'History{' + repr(self.visits) + '}'


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


# TODO sort just in case? not sure..
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

