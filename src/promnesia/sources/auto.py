"""
- discovers files recursively
- guesses the format (orgmode/markdown/json/etc) by the extension/MIME type
"""

import csv
from concurrent.futures import ProcessPoolExecutor as Pool
from datetime import datetime
import itertools
import json
import os
from typing import Optional, Iterable, Union, List, Tuple, NamedTuple, Sequence, Iterator, Iterable, Callable, Any, Dict, Set
from fnmatch import fnmatch
from pathlib import Path
from functools import lru_cache, wraps
import warnings

import pytz

from ..common import Visit, Url, PathIsh, get_logger, Loc, get_tmpdir, extract_urls, Extraction, Results, mime, traverse, file_mtime
from ..config import use_cores
from ..py37 import nullcontext


from .filetypes import EUrl


def _collect(thing, path: List[str], result: List[EUrl]):
    if isinstance(thing, str):
        ctx: Ctx = tuple(path) # type: ignore
        result.extend([EUrl(url=u, ctx=ctx) for u in extract_urls(thing)])
    elif isinstance(thing, list):
        path.append('[]')
        for x in thing:
            _collect(x, path, result)
        path.pop()
    elif isinstance(thing, dict):
        for k, v in thing.items():
            path.append(k)
            _collect(k, path, result)
            _collect(v, path, result)
            path.pop()
    else:
        pass


# TOOD mm. okay, I suppose could use kython consuming thingy?..
def collect_from(thing) -> List[EUrl]:
    uuu: List[EUrl] = []
    path: List[str] = []
    _collect(thing, path, uuu)
    return uuu


Urls = Iterator[EUrl]

def _csv(path: Path) -> Urls:
    # TODO these could also have Loc to be fair..
    with path.open() as fo:
        # TODO shit need to urldecode
        reader = csv.DictReader(fo)
        for line in reader:
            yield from collect_from(line)


def _json(path: Path) -> Urls:
    jj = json.loads(path.read_text())
    yield from collect_from(jj)


def _plaintext(path: Path) -> Results:
    from . import shellcmd
    from .plaintext import extract_from_path
    yield from shellcmd.index(extract_from_path(path))


# TODO think about the type
# TODO could pass fallback reason to the results as well?
def fallback(ex):
    """Falls back to plaintext in case of issues"""

    fallback_active: Dict[Any, bool] = {}
    @wraps(ex)
    def wrapped(path: Path):
        nonlocal fallback_active
        do_fallback = fallback_active.get(ex, False)

        if not do_fallback:
            try:
                it = ex(path)
                # ugh. keeping yeild in the try section is not ideal, but need this because of lazy yield semantics
                yield from it
            except ModuleNotFoundError as me:
                # TODO ugh. need to figure out how to attach cause/traceback
                logger = get_logger()
                logger.exception(me)
                logger.warn('while indexing "%s": %s not found, falling back to plaintext! "pip3 install --user %s" for better support!', path, me.name, me.name)
                yield me

                fallback_active[ex] = True
                do_fallback = True
        if do_fallback:
            yield from _plaintext(path)
    return wrapped


@fallback
def _markdown(path: Path) -> Results:
    from . import markdown
    yield from markdown.extract_from_file(path)


@fallback
def _html(path: Path) -> Results:
    from . import html
    yield from html.extract_from_file(path)


@fallback
def _org(path: Path) -> Results:
    from . import org
    return org.extract_from_file(path)


from .filetypes import TYPE2IDX, type2idx, IGNORE, CODE

TYPE2IDX.update({
    'application/json': _json,
    '.json'           : _json,
    '.ipynb'          : _json,

    '.csv'           : _csv,
    'application/csv': _csv,

    '.org'        : _org,
    '.org_archive': _org,

    '.md'         : _markdown,
    '.markdown'   : _markdown,

    'text/plain'  : _plaintext,
    '.txt'        : _plaintext,
    '.page'       : _plaintext,
    '.rst'        : _plaintext,


    # TODO doesn't work that great; weird stuff like
    # builtins.ImportError.name|2019-07-10T12:12:35.584510+00:00|names::ImportError::node::names::name::node::fullname
    # TODO could have stricter url extraction for that; always using http/https?
    # '.ipynb'      : _json,

    '.html'    : _html,
    'text/html': _html,
    'text/xml' : _plaintext,
})

for t in CODE:
    TYPE2IDX[t] = _plaintext
# TODO ok, mime doesn't really tell between org/markdown/etc anyway


Replacer = Optional[Callable[[str], str]]

def index(
        *paths: Union[PathIsh],
        ignored: Union[Sequence[str], str]=(),
        follow=True,
        replacer: Replacer=None,
) -> Results:
    '''
    path   : a path or list of paths to recursively index
    ignored: a glob or list of globs to exclude from indexing
    follow : whether to follow symlinks or not
    '''
    # TODO document replacer?
    ignored = (ignored,) if isinstance(ignored, str) else ignored
    for p in paths:
        # TODO for displaying maybe better not to expand/absolute, but need it for correct mime handling
        apath = Path(p).expanduser().resolve().absolute()
        root = apath if apath.is_dir() else None
        opts = Options(
            ignored=ignored,
            follow=follow,
            replacer=replacer,
            root=root,
        )
        yield from _index(apath, opts=opts)

class Options(NamedTuple):
    ignored: Sequence[str]
    follow: bool
    # TODO option to add ignores? not sure..
    # TODO I don't like this replacer thing... think about removing it
    replacer: Replacer
    root: Optional[Path]=None


def _index_file_aux(path: Path, opts: Options):
    # just a helper for the concurrent version (the generator isn't picklable)
    try:
        return list(_index_file(path, opts=opts))
    except Exception as e:
        # possible due to unavoidable race conditions
        return e


def _index(path: Path, opts: Options) -> Results:
    logger = get_logger()

    cores = use_cores()
    if cores is None: # do not use cores
        pool = nullcontext()
        mapper = map # dummy pool
    else:
        workers = None if cores == 0 else cores
        pool = Pool(workers) # type: ignore
        mapper = pool.map # type: ignore

    # iterate over resolved paths, to avoid duplicates
    def rit() -> Iterable[Path]:
        it = traverse(path, follow=opts.follow)
        for p in it:
            if any(fnmatch(str(p), o) for o in opts.ignored):
                # TODO not sure if should log here... might end up with quite a bit of logs
                logger.debug('ignoring %s: user ignore rules', p)
                continue
            if any(i in p.parts for i in IGNORE): # meh, not very efficient.. pass to traverse??
                logger.debug('ignoring %s: default ignore rules', p)
                continue

            p = p.resolve()
            if not os.path.exists(p):
                logger.debug('ignoring %s: broken symlink?', p)
                continue

            yield p

    from more_itertools import unique_everseen
    it = unique_everseen(rit())

    with pool:
        for r in mapper(_index_file_aux, it, itertools.repeat(opts)):
            if isinstance(r, Exception):
                yield r
            else:
                yield from r


def by_path(pp: Path):
    suf = pp.suffix.lower()
    # firt check suffixes, it's faster
    s = type2idx(suf)
    if s is not None:
        return s, None
    # then try with mime
    pm = mime(pp)
    if pm is not None:
        return type2idx(pm), pm
    else:
        return None, None


def _index_file(pp: Path, opts: Options) -> Results:
    logger = get_logger()
    # TODO use kompress?
    # TODO not even sure if it's used...
    suf = pp.suffix.lower()

    if suf == '.xz': # TODO zstd?
        import lzma
        uname = pp.name[:-len('.xz')]
        uncomp = Path(get_tmpdir().name) / uname
        with lzma.open(pp, 'rb') as cf:
            with uncomp.open('wb') as fb:
                fb.write(cf.read())
        yield from _index(path=uncomp, opts=opts)
        return

    ip, pm = by_path(pp)
    if ip is None:
        # TOOD use warning (with mime/ext as key?)
        # TODO only log once? # hmm..
        msg = f'No extractor for suffix {suf}, mime {pm}'
        warnings.warn(msg)
        yield RuntimeError(msg + f', path {pp}')
        return

    logger.debug('indexing via %s: %s', ip.__name__, pp)
    indexer: Union[Urls, Results] = ip(pp) # type: ignore
    # TODO careful, filter out obviously not plaintext? maybe mime could help here??

    root = opts.root
    fallback_dt = file_mtime(pp)
    fallback_loc = Loc.file(pp)
    replacer = opts.replacer
    for r in indexer:
        if isinstance(r, Exception):
            yield r
            continue
        if isinstance(r, EUrl):
            v = Visit(
                url=r.url,
                dt=fallback_dt,
                locator=fallback_loc,
                context='::'.join(r.ctx),
            )
        else:
            v = r

        loc = v.locator
        if loc is not None and root is not None:
            # meh. but it works
            # todo potentially, just use dataclasses instead...
            loc = loc._replace(title=loc.title.replace(str(root) + '/', ''))
            v = v._replace(locator=loc)

        if replacer is not None:
            upd: Dict[str, Any] = {}
            href = v.locator.href
            if href is not None:
                upd['locator'] = v.locator._replace(href=replacer(href), title=replacer(v.locator.title))
            ctx = v.context
            if ctx is not None:
                # TODO in context, http is unnecessary
                upd['context'] = replacer(ctx)
            v = v._replace(**upd)
        yield v
