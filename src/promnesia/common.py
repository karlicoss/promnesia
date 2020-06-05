from collections.abc import Sized
from datetime import datetime, date
import os
import re
from typing import NamedTuple, Set, Iterable, Dict, TypeVar, Callable, List, Optional, Union, Any, Collection, Sequence, Tuple, TypeVar
from pathlib import Path
from glob import glob
import itertools
import logging
from functools import lru_cache
import traceback
import pytz
import warnings

from .cannon import CanonifyException, canonify


T = TypeVar('T')
Res = Union[T, Exception]

PathIsh = Union[str, Path]

Url = str
SourceName = str
DatetimeIsh = Union[datetime, date]
Context = str
Second = int

# TODO hmm. arguably, source and context are almost same things...
class Loc(NamedTuple):
    title: str
    href: Optional[str]=None

    @classmethod
    def make(cls, title: str, href: Optional[str]=None) -> 'Loc':
        return cls(title=title, href=href)

    @classmethod
    def file(cls, path: PathIsh, line: Optional[int]=None, relative_to: Optional[Path]=None):
        ll = '' if line is None else f':{line}'
        # todo loc should be url encoded? dunno.
        # or use line=? eh. I don't know. Just ask in issues.
        handler = _detect_mime_handler()

        rel = Path(path)
        if relative_to is not None:
            try:
                # making it relative is a bit nicer for display
                rel = rel.relative_to(relative_to)
            except Exception as e:
                pass # TODO log?
        loc = f'{rel}{ll}'
        return cls.make(
            title=loc,
            href=f'{handler}{loc}'
        )

    # TODO need some uniform way of string conversion
    # but generally, it will be
    # (url|file)(linenumber|json_path|anchor)

@lru_cache(1)
def _detect_mime_handler() -> str:
    def exists(what: str) -> bool:
        from subprocess import run, PIPE
        try:
            r = run(f'xdg-mime query default x-scheme-handler/{what}'.split(), stdout=PIPE)
        except FileNotFoundError:
            warnings.warn("No xdg-mime on your OS! If you're on OSX, perhaps you can help me! https://github.com/karlicoss/open-in-editor/issues/1")
            return False
        if r.returncode > 0:
            warnings.warn('xdg-mime failed') # hopefully rest is in stderr
            return False
        # todo not sure if should check=True or something
        handler = r.stdout.decode('utf8').strip()
        return len(handler) > 0

    # 1. detect legacy 'emacs:' handler (so it doesn't break for existing users)
    result = None
    if exists('emacs'):
        warnings.warn('''
        'emacs:' handler is deprecated!
        Please use newer version at https://github.com/karlicoss/open-in-editor
        And remove the old one (most likely, rm ~/.local/share/applications/mimemacs.desktop && update-desktop-database ~/.local/share/applications).
'''.rstrip())
        result = 'emacs:'

    # 2. now try to use newer editor:// thing

    # TODO would be nice to collect warnings and display at the end
    if not exists('editor'):
        warnings.warn('''
        You might want to install https://github.com/karlicoss/open-in-editor
        So you can jump you your text files straight from the browser
'''.rstrip())
    else:
        result = 'editor://'

    if result is None:
        result = 'editor://'

    return result


# TODO serialize unions? Might be a bit mad...
class Visit(NamedTuple):
    url: Url
    # TODO back to DatetimeIsh, but somehow make compatible to dbcache?
    dt: datetime
    locator: Loc
    context: Optional[Context] = None
    duration: Optional[Second] = None
    # TODO shit. I need to insert it in chrome db....
    # TODO gonna be hard to fill retroactively.
    # spent: Optional[Second] = None
    debug: Optional[str] = None

Extraction = Union[Visit, Exception]
Result = Extraction # TODO extraction is a bit too long? deprecate?
Results = Iterable[Result]


class DbVisit(NamedTuple):
    norm_url: Url
    orig_url: Url
    dt: datetime
    locator: Loc
    src: Optional[SourceName] = None
    context: Optional[Context] = None
    duration: Optional[Second] = None

    @staticmethod
    def make(p: Visit, src: SourceName) -> Res['DbVisit']:
        try:
            if isinstance(p.dt, datetime):
                dt = p.dt
            elif isinstance(p.dt, date):
                # TODO that won't be with timezone..
                dt = datetime.combine(p.dt, datetime.min.time()) # meh..
            else:
                raise AssertionError(f'unexpected date: {p.dt}, {type(p.dt)}')
        except Exception as e:
            return e

        try:
            nurl = canonify(p.url)
        except Exception as e:
            return e

        return DbVisit(
            # TODO shit, can't handle errors properly here...
            norm_url=nurl,
            orig_url=p.url,
            dt=dt,
            locator=p.locator,
            context=p.context,
            duration=p.duration,
            src=src,
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


def get_logger() -> logging.Logger:
    return logging.getLogger("promnesia")

# TODO do i really need to inherit this??
class History(Sized):
    # TODO I guess instead filter on DbVisit making site?
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

    def __init__(self, *, src: SourceName):
        self.vmap: Dict[Visit, DbVisit] = {}
        # TODO err... why does it map from previsit???
        self.logger = get_logger()
        self.src = src

    # TODO mm. maybe history should get filters from some global config?
    # wonder how okay is it to set class attribute..

    @classmethod
    def filtered(cls, url: Url) -> bool:
        for f in cls.FILTERS:
            if f(url):
                return True
        return False

    @property
    def visits(self) -> List[DbVisit]:
        return list(self.vmap.values())

    def register(self, v: Visit) -> Optional[Exception]:
        # TODO should we filter before normalising? not sure...
        if History.filtered(v.url):
            return None

        # TODO perhaps take normalised into account here??
        if v in self.vmap:
            return None

        res = DbVisit.make(v, src=self.src)
        if isinstance(res, CanonifyException):
            self.logger.error('error while canonnifying %s... ignoring', v)
            self.logger.exception(res)
            return None
        elif isinstance(res, Exception):
            return res
        else:
            db_visit = res

        self.vmap[v] = db_visit
        return None
        # TODO hmm some filters make sense before stripping off protocol...

    ## only used in tests?..
    def _nmap(self):
        from itertools import groupby
        key = lambda x: x.norm_url
        return {k: list(g) for k, g in groupby(sorted(self.visits, key=key), key=key)}

    def __len__(self) -> int:
        return len(self._nmap())

    def __contains__(self, url) -> bool:
        return url in self._nmap()

    def __getitem__(self, url: Url):
        return self._nmap()[url]
    #

    def __repr__(self):
        return 'History{' + repr(self.visits) + '}'


# kinda singleton
@lru_cache(1)
def get_tmpdir():
    import tempfile
    tdir = tempfile.TemporaryDirectory(suffix="promnesia")
    return tdir

# TODO use mypy literal?
Syntax = str


@lru_cache(None)
def _get_extractor(syntax: Syntax):
    from urlextract import URLExtract # type: ignore
    u = URLExtract()
    # https://github.com/lipoja/URLExtract/issues/13
    if syntax in {'org', 'orgmode', 'org-mode'}: # TODO remove hardcoding..
        u._stop_chars_right |= {'[', ']'}
        u._stop_chars_left  |= {'[', ']'}
    elif syntax in {'md', 'markdown'}:
        pass
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
def _extract_line_urls(*, s: str, syntax: Syntax) -> List[str]:
    # TODO unit test for escaped urls.. or should it be in normalise instead?
    if len(s.strip()) == 0:
        return [] # optimize just in case..

    # TODO special handling for org links

    # TODO fuck. doesn't look like it's handling multiple urls in same line well...
    # ("python.org/one.html python.org/two.html",
    # hopefully ok... I guess if there are spaces in url we are fucked anyway..
    extractor = _get_extractor(syntax=syntax)
    urls: List[str] = []
    for x in s.split():
        urls.extend(extractor.find_urls(x))

    return [sanitize(u) for u in urls]


def _extract_urls(*, s: str, syntax: Syntax) -> Iterable[Url]:
    for line in s.splitlines():
        yield from _extract_line_urls(s=line, syntax=syntax)


def extract_urls(s: str, syntax: Syntax='') -> List[Url]:
    return list(_extract_urls(s=s, syntax=syntax))


# TODO maybe belongs to HPI?
def from_epoch(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=pytz.utc)


class PathWithMtime(NamedTuple):
    path: Path
    mtime: float

    @classmethod
    def make(cls, p: Path):
        return cls(
            path=p,
            mtime=p.stat().st_mtime,
        )


# todo not sure about this...
def _guess_name(thing) -> str:
    from types import ModuleType
    guess = ''
    if isinstance(thing, ModuleType):
        guess = thing.__name__
    elif callable(thing):
        guess = thing.__module__

    dflt = 'promnesia.sources.'
    if guess.startswith(dflt):
        # meh
        guess = guess[len(dflt):]
    return guess


def _get_index_function(thing):
    # see config_tests
    # not sure about this
    if hasattr(thing, 'index'):
        thing = getattr(thing, 'index')
    return thing


class Source:
    # TODO make sure it works with empty src?
    # TODO later, make it properly optional?
    def __init__(self, ff, *args, src: SourceName='', name: SourceName='', **kwargs) -> None:
        self.ff = _get_index_function(ff)
        self.args = args
        self.kwargs = kwargs
        if src is not None:
            warnings.warn("'src' argument is deprecated, please use 'name' instead", DeprecationWarning)
        try:
            name_guess = _guess_name(ff)
        except:
            # todo warn?
            name_guess = ''
        self.src = name or src or name_guess

    @property
    def name(self) -> str:
        # todo deprecate src..
        return self.src

# TODO deprecated
Indexer = Source


# TODO do we really need it?
def previsits_to_history(extractor, *, src: SourceName) -> Tuple[List[DbVisit], List[Exception]]:
    ex = extractor
    # TODO isinstance wrapper?
    # TODO make more defensive?
    logger = get_logger()

    log_info: str
    if isinstance(ex, Indexer):
        log_info = f'{ex.ff.__module__}:{ex.ff.__name__} {ex.args} {ex.kwargs} ...'
        extr = lambda: ex.ff(*ex.args, **ex.kwargs)
    else:
        # TODO if it's a lambda?
        log_info = f'{ex.__module__}:{ex.__name__}'
        extr = ex


    logger.info('extracting via %s ...', log_info)

    h = History(src=src)
    errors = []
    try:
        previsits = list(extr())
    except Exception as e:
        logger.exception(e)
        return [], [e]

    for p in previsits:
        if isinstance(p, Exception):
            errors.append(p)
            parts = ['indexer emitted exception\n']
            # eh, exception type is ignored by format_exception completely, apparently??
            parts.extend(traceback.format_exception(Exception, p, p.__traceback__))
            logger.error(''.join(parts))
            continue

        # TODO check whether it's filtered before construction? probably doesn't really impact
        res = h.register(p)
        if isinstance(res, Exception):
            logger.exception(res)
            errors.append(res)

    # TODO should handle filtering properly?
    logger.info('extracting via %s: got %d visits', log_info, len(h))
    return h.visits, errors


# not sure if necessary anymore?
# NOTE: used in configs...
def last(path: PathIsh, *parts: str) -> Path:
    import os.path
    pp = os.path.join(str(path), *parts)
    return Path(max(glob(pp, recursive=True)))


from .kython.klogging2 import setup_logger

def echain(ex: Exception, cause: Exception) -> Exception:
    ex.__cause__ = cause
    return ex


def slugify(x: str) -> str:
    # https://stackoverflow.com/a/38766141/706389
    import re
    valid_file_name = re.sub(r'[^\w_.)( -]', '', x)
    return valid_file_name


# todo cache?
def appdirs():
    under_test = os.environ.get('PYTEST_CURRENT_TEST') is not None
    # todo actually use test name?
    name = 'promnesia-test' if under_test else 'promnesia'
    import appdirs as ad # type: ignore[import]
    return ad.AppDirs(appname=name)


def default_output_dir() -> Path:
    return Path(appdirs().user_data_dir)

# TODO deprecate..
PreVisit = Visit
