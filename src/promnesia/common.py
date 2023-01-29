from collections.abc import Sized
from contextlib import contextmanager
from datetime import datetime, date
import os
from typing import NamedTuple, Set, Iterable, Dict, TypeVar, Callable, List, Optional, Union, Any, Collection, Sequence, Tuple, TypeVar, TYPE_CHECKING
from pathlib import Path
from glob import glob
import itertools
from more_itertools import intersperse
import logging
from functools import lru_cache
import shutil
from timeit import default_timer as timer
from types import ModuleType
import warnings

import pytz

from .cannon import canonify


_is_windows = os.name == 'nt'

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
    def file(cls, path: PathIsh, line: Optional[int]=None, relative_to: Optional[Path]=None) -> 'Loc':
        lstr = '' if line is None else f':{line}'
        # todo loc should be url encoded? dunno.
        # or use line=? eh. I don't know. Just ask in issues.

        # todo: handler has to be overridable by config. This is needed for docker, but also for a "as a service" install, where the sources would be available on some remote webserver
        # maybe it should be treated as a format string, so that {line} may be a part of the result or not.
        # for local usage, editor:///file:line works, but if the txt file is only available through http, it breaks.
        #if get_config().MIME_HANDLER:
        #   handler = get_config().MIME_HANDLER
        #if True:
        #    handler =  'editor:///home/koom/promnesia/docker/'
        #else:
        handler = _detect_mime_handler()

        rel = Path(path)
        if relative_to is not None:
            try:
                # making it relative is a bit nicer for display
                rel = rel.relative_to(relative_to)
            except Exception as e:
                pass # todo log/warn?
        loc = f'{rel}{lstr}'
        return cls.make(
            title=loc,
            href=f'{handler}{path}{lstr}'
        )

    # TODO need some uniform way of string conversion
    # but generally, it will be
    # (url|file)(linenumber|json_path|anchor)

@lru_cache(1)
def _detect_mime_handler() -> str:
    def exists(what: str) -> bool:
        from .compat import run, PIPE
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
        So you can jump to your text files straight from the browser
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

Result = Union[Visit, Exception]
Results = Iterable[Result]
Extractor = Callable[[], Results]

Extraction = Result  # TODO deprecate!

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
            # hmm, mypy gets a bit confused here.. presumably because datetime is always datetime (but date is not datetime)
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


from .logging import LazyLogger
logger = LazyLogger('promnesia', level='DEBUG')

def get_logger() -> logging.Logger:
    # deprecate? no need since logger is lazy already
    return logger



import tempfile
# kinda singleton
@lru_cache(1)
def get_tmpdir() -> tempfile.TemporaryDirectory:
    # todo use appdirs?
    tdir = tempfile.TemporaryDirectory(suffix="promnesia")
    return tdir

# TODO use mypy literal?
Syntax = str


@lru_cache(None)
def _get_urlextractor(syntax: Syntax):
    from urlextract import URLExtract # type: ignore
    u = URLExtract()
    # https://github.com/lipoja/URLExtract/issues/13
    if syntax in {'org', 'orgmode', 'org-mode'}: # TODO remove hardcoding..
        # handle org-mode links properly..
        u._stop_chars_right |= {'[', ']'}
        u._stop_chars_left  |= {'[', ']'}
    elif syntax in {'md', 'markdown'}:
        pass
    # u._stop_chars_right |= {','}
    # u._stop_chars_left  |= {','}
    return u


def _sanitize(url: str) -> str:
    # TODO not sure it's a really good idea.. but seems easiest now
    # TODO have whitelisted urls that allow trailing parens??
    url = url.strip(',.…\\')
    if 'wikipedia' not in url:
        # urls might end with parens en.wikipedia.org/wiki/Widget_(beer)
        url = url.strip(')')
    return url


def iter_urls(s: str, *, syntax: Syntax='') -> Iterable[Url]:
    urlextractor = _get_urlextractor(syntax=syntax)
    # note: it also has get_indices, might be useful
    for u in urlextractor.gen_urls(s):
        yield _sanitize(u)


def extract_urls(s: str, *, syntax: Syntax='') -> List[Url]:
    return list(iter_urls(s=s, syntax=syntax))


def from_epoch(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=pytz.utc)


def join_tags(tags: Iterable[str]) -> str:
    """
    Append `#` in fron of each tag and joins them with a space in between

    >>> join_tags(["foo", "bar"])
    '#foo #bar'
    >>> join_tags(["", " ", None])
    ''
    """
    return " ".join(f"#{t}" for t in tags if t and t.strip())


class PathWithMtime(NamedTuple):
    path: Path
    mtime: float

    @classmethod
    def make(cls, p: Path) -> 'PathWithMtime':
        return cls(
            path=p,
            mtime=p.stat().st_mtime,
        )


# like an Extractor, but with args not bound yet
PreExtractor = Callable[..., Results]


PreSource = Union[
    PreExtractor,
    ModuleType,   # module with 'index' functon defined in it
]


# todo not sure about this...
def _guess_name(thing: PreSource) -> str:
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


def _get_index_function(sourceish: PreSource) -> PreExtractor:
    # see config_tests
    res: PreExtractor
    if hasattr(sourceish, 'index'):  # must be a module
        res = getattr(sourceish, 'index')
    else:
        res = sourceish  # type: ignore[assignment]
    return res


class Source:
    # TODO make sure it works with empty src?
    # TODO later, make it properly optional?
    def __init__(self, ff: PreSource, *args, src: SourceName='', name: SourceName='', **kwargs) -> None:
        # NOTE: in principle, would be nice to make the Source countructor to be as dumb as possible
        # so we could move _get_index_function inside extractor lambda
        # but that way we get nicer error reporting
        # e.g. we can print out module/function name and arguments (see .description)
        # it's kinda justified in the sense that an error with the Source itself is a bit different
        # from the error coming from one of the visits within a source
        self.ff: PreExtractor = _get_index_function(ff)
        self.args = args
        self.kwargs = kwargs
        self.extractor: Extractor = lambda: self.ff(*self.args, **self.kwargs)
        if src is not None:
            warnings.warn("'src' argument is deprecated, please use 'name' instead", DeprecationWarning)
        try:
            name_guess = _guess_name(ff)
        except:
            # todo warn?
            name_guess = ''
        self.name = name or src or name_guess

    @property
    def description(self) -> str:
        return f'{getattr(self.ff, "__module__", None)}:{getattr(self.ff, "__name__", None)} {self.args} {self.kwargs}'

    @property
    def src(self) -> str:
        # TODO deprecated!
        return self.name

# TODO deprecated
Indexer = Source


# not sure if necessary anymore?
# NOTE: used in configs...
def last(path: PathIsh, *parts: str) -> Path:
    import os.path
    pp = os.path.join(str(path), *parts)
    return Path(max(glob(pp, recursive=True)))


from .logging import setup_logger

from copy import copy
def echain(ex: Exception, cause: Exception) -> Exception:
    e = copy(ex)
    e.__cause__ = cause
    # right.. even if we attach cause it doesn't help much because when we return/yield exception, we lose the stacktrace
    # so only 'ex' gets logged, cause is completely lost
    # hopefully this is safe? at least on runtimeerrors
    # might also do something smarter and collapse if both are strings or something..
    e.args += cause.args
    return e


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
    # TODO: on Windows, there are two extra subdirectories (<AppAuthor>\<AppName>)
    # perhaps makes sense to create it here with parents to avoid issues downstream?
    return Path(appdirs().user_data_dir)


def default_cache_dir() -> Path:
    return Path(appdirs().user_cache_dir)


# make it lazy, otherwise it might crash on module import (e.g. on Windows)
# ideally would be nice to fix it properly https://github.com/ahupp/python-magic#windows
@lru_cache(1)
def _magic() -> Callable[[PathIsh], Optional[str]]:
    logger = get_logger()
    try:
        import magic # type: ignore
    except Exception as e:
        logger.exception(e)
        defensive_msg: Optional[str] = None
        if isinstance(e, ModuleNotFoundError) and e.name == 'magic':
            defensive_msg = "python-magic is not detected. It's recommended for better file type detection (pip3 install --user python-magic). See https://github.com/ahupp/python-magic#installation"
        elif isinstance(e, ImportError):
            emsg = getattr(e, 'msg', '') # make mypy happy
            if 'failed to find libmagic' in emsg: # probably the actual library is missing?...
                defensive_msg = "couldn't import magic. See https://github.com/ahupp/python-magic#installation"
        if defensive_msg is not None:
            logger.warning(defensive_msg)
            warnings.warn(defensive_msg)
            return lambda path: None # stub
        else:
            raise e
    else:
        mm = magic.Magic(mime=True)
        return mm.from_file


# todo annoying... can't return module in mypy
@lru_cache(1)
def _mimetypes():
    import mimetypes
    mimetypes.init()
    return mimetypes


def mime(path: PathIsh) -> Optional[str]:
    ps = str(path)
    mimetypes = _mimetypes()
    # first try mimetypes, it's only using the filename without opening the file
    pm, _ = mimetypes.guess_type(ps)
    if pm is not None:
        return pm
    # next, libmagic, it might access the file, so a bit slower
    magic = _magic()
    return magic(ps)


def find_args(root: Path, follow: bool, ignore: List[str]=[]) -> List[str]:
    prune_dir_args = []
    ignore_file_args = []
    if ignore:
        # -name {name} for all the file/directories in ignore
        ignore_names = [['-name', n] for n in ignore]
        # OR (-o) all the names together and flatten
        ignore_names_l = list(itertools.chain(*intersperse(['-o'], ignore_names)))
        # Prune all of those directories, and make the entire clause evaluate to false
        # (so that it doesn't match anything and make find print)
        prune_dir_args = ['-type', 'd', '-a', '(', *ignore_names_l, ')', '-prune', '-false', '-o']
        # Also ignore any files with the names as well
        ignore_file_args = ['-a', '-not', '(', *ignore_names_l, ')']

    return [
        *(['-L'] if follow else []),
        str(root),
        *prune_dir_args,
        '-type', 'f',
        *ignore_file_args
    ]


def fdfind_args(root: Path, follow: bool, ignore: List[str]=[]) -> List[str]:
    from .config import extra_fd_args

    ignore_args = []
    if ignore:
        # Add a statement that excludes the folder
        ignore_args = [['--exclude', f'{n}'] for n in ignore]
        # Flatten the list of lists
        ignore_args_l = list(itertools.chain(*ignore_args))

    return [
        *extra_fd_args(),
        *ignore_args_l,
        *(['--follow'] if follow else []),
        '--type', 'f',
        '.',
        str(root),
    ]


def traverse(root: Path, *, follow: bool=True, ignore: List[str]=[]) -> Iterable[Path]:
    if not root.is_dir():
        yield root
        return

    # todo does windows even have symlinks??
    if _is_windows:
        # on windows could use 'forfiles'... but probably easier not to bother for now
        # todo coild use followlinks=True? walk could end up in infinite loop?
        for r, dirs, files in os.walk(root):
            # Remove dirs specified in ignore (clone dirs() as we have to remove in place)
            for i, d in enumerate(list(dirs)):
                if d in ignore:
                    del dirs[i]
            yield from (Path(r) / f for f in files if f not in ignore)
        return

    from .compat import Popen, PIPE
    cmd = ['find', *find_args(root, follow=follow, ignore=ignore)]
    # try to use fd.. it cooperates well with gitignore etc, also faster than find
    for x in ('fd', 'fd-find', 'fdfind'): # has different names on different dists..
        if shutil.which(x):
            cmd = [x, *fdfind_args(root, follow=follow, ignore=ignore)]
            break
    else:
        warnings.warn("'fdfind' is recommended for the best indexing performance. See https://github.com/sharkdp/fd#installation. Falling back to 'find'")

    logger.debug('running: %s', cmd)
    # TODO split by \0?
    # TODO should it check return code? not sure
    with Popen(cmd, stdout=PIPE) as p:
        out = p.stdout
        assert out is not None
        for line in out:
            fpath = Path(line.decode('utf8').strip())
            yield fpath


@lru_cache(1)
def get_system_zone() -> str:
    try:
        import tzlocal
        # note: tzlocal mypy stubs aren't aware of api change yet (see https://github.com/python/typeshed/issues/6038)
        try:
            # 4.0 way
            return tzlocal.get_localzone_name() # type: ignore[attr-defined]
        except AttributeError as e:
            # 2.0 way
            zone = tzlocal.get_localzone().zone  # type: ignore[attr-defined]
            # see https://github.com/python/typeshed/blame/968fd6d01d23470e0c8368e7ee7c43f54aaedc0e/stubs/pytz/pytz/tzinfo.pyi#L6
            # it says all concrete instances should not be None
            assert zone is not None
            return zone
    except Exception as e:
        logger.exception(e)
        logger.error("Couldn't determine system timezone. Falling back to UTC. Please report this as a bug!")
        return 'UTC'


@lru_cache(1)
def get_system_tz() -> pytz.BaseTzInfo:
    zone = get_system_zone()
    try:
        return pytz.timezone(zone)
    except Exception as e:
        logger.exception(e)
        logger.error(f"Unknown time zone %s. Falling back to UTC. Please report this as a bug!", zone)
        return pytz.utc

# used in misc/install_server.py
def root() -> Path:
    r = Path(__file__).absolute().parent.parent.parent
    assert (r / 'src').exists()
    return r


def file_mtime(path: PathIsh) -> datetime:
    tz = get_system_tz()
    return datetime.fromtimestamp(Path(path).stat().st_mtime, tz=tz)


def now_tz() -> datetime:
    return datetime.now(tz=get_system_tz())


def user_config_file() -> Path:
    if "PROMNESIA_CONFIG" in os.environ:
        return Path(os.environ["PROMNESIA_CONFIG"])
    else:
        return Path(appdirs().user_config_dir) / 'config.py'


def default_config_path() -> Path:
    cfg = Path('config.py')
    if cfg.exists():
        # todo ugh. might be nice to warn, but then it will always spam in cli...
        # eh. not sure if it's a good idea, but whatever, it was the old behaviour
        return cfg.absolute()
    else:
        return user_config_file()
    # TODO need to test this..


@contextmanager
def measure(tag: str='', *, logger, unit: str='ms'):
    before = timer()
    yield lambda: timer() - before
    after = timer()
    secs = after - before
    mult = {'s': 1, 'ms': 10**3, 'us': 10**6}[unit]
    xx = secs * mult
    logger.debug(f'[{tag}]: {xx:.1f}{unit} elapsed')
