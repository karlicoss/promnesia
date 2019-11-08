"""
Tries to index as much as it can:

- TODO walks up the filesystem hierarchy
- guesses org/markdown/json/etc by extension or mime type

"""

import csv
from datetime import datetime
import json
from typing import Optional, Iterable, Union, List, Tuple, NamedTuple, Sequence, Iterator
from fnmatch import fnmatch
from pathlib import Path
from functools import lru_cache

import pytz

from ..common import Visit, Url, PathIsh, get_logger, Loc, get_tmpdir, extract_urls, Extraction


@lru_cache(1)
def _magic():
    import magic # type: ignore
    return magic.Magic(mime=True)


def mime(path: PathIsh) -> str:
    return _magic().from_file(str(path))

Ctx = Sequence[str]

class EUrl(NamedTuple):
    url: Url
    ctx: Ctx # TODO ctx here is more like a Loc


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

# TODO use magic and mimes maybe?


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


def _plaintext(path: Path) -> Iterator[Extraction]:
    from . import shellcmd
    from .plaintext import extract_from_path
    logger = get_logger()
    yield from shellcmd.extract(extract_from_path(path))


def _markdown(path: Path) -> Iterator[Extraction]:
    # TODO for now handled as plaintext
    yield from _plaintext(path)


@lru_cache(1)
def _extract_org():
    try:
        from .org import extract_from_file
        return extract_from_file
    except ImportError as e:
        logger = get_logger()
        logger.exception(e)
        logger.warning('Falling back to plaintext for Org mode! Install orgparse for better support!')
        return None


def _org(path: Path) -> Iterator[Extraction]:
    eo = _extract_org()
    if eo is None:
        yield from _plaintext(path)
    else:
        res = list(eo(path))
        yield from res


SMAP = {
    'application/json': _json,
    '.json'           : _json,

    '.csv'        : _csv,

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

    # TODO not sure about these:
    'html': None,
    'text/html': None,
    'text/xml': None,
    'text/x-python': None,
    'text/x-tex': None,
    'text/x-lisp': None,
    'text/x-shellscript': None,
    'text/x-java': None,
    'text/troff': None,
    'text/x-c': None,
    'text/x-c++': None,
    'text/x-makefile': None,
    # TODO could reuse magic lib?

    '.tex': None, # TODO not sure..
    '.css': None,
    '.sh' : None,
    '.js' : None,
    '.hs' : None,
    '.bat': None,
    '.pl' : None,
    '.h'  : None,
    '.rs' : None,


    # TODO possible in theory?
    '.ppt' : None,
    '.pptx': None,
    '.xlsx': None,
    '.doc' : None,
    '.docx': None,
    '.ods' : None,
    '.odt' : None,
    '.rtf' : None,
    '.epub': None,
    '.pdf' : None,
    '.vcf' : None,
    '.djvu': None,
    '.dvi' : None,
    'application/msword': None,
    'application/postscript': None,
    'message/rfc822': None,

    # TODO compressed?
    'application/octet-stream': None,
    'application/zip': None,
    'application/x-tar': None,
    'application/gzip': None,
    'application/x-sqlite3': None,
    'application/x-archive': None,
    'application/x-pie-executable': None,
    '.o'  : None,
    'image/jpeg': None,
    '.jpg': None,
    '.png': None,
    'image/png': None,
    '.gif': None,
    '.svg': None,
    '.ico': None,
    'inode/x-empty': None,
    '.class': None,
    '.jar': None,
    '.mp3': None,
    '.mp4': None,
}
# TODO ok, mime doesn't really tell between org/markdown/etc anyway

IGNORE = [
    '.git',
    '.mypy_cache',
    '.pytest_cache',
    'node_modules',
    '__pycache__',
    '.tox',
    '.stack-work',
    # TODO use ripgrep?

    # TODO not sure about these:
    '.gitignore',
    '.babelrc',
]


def index(path: Union[List[PathIsh], PathIsh], *, ignored: Union[Sequence[str], str]=(), follow=True) -> Iterator[Extraction]:
    # TODO *args?
    # TODO meh, unify with glob traversing..
    paths = path if isinstance(path, list) else [path]
    ignored = (ignored,) if isinstance(ignored, str) else ignored
    opts = Options(
        ignored=ignored,
        follow=follow,
    )
    for p in paths:
        yield from _index(Path(p), opts=opts)


class Options(NamedTuple):
    ignored: Sequence[str]
    follow: bool
    # TODO option to add ignores? not sure..


def _index(path: Path, opts: Options) -> Iterator[Extraction]:
    logger = get_logger()
    pp = path # ugh, for historic reasons..

    if pp.name in IGNORE:
        logger.debug('ignoring %s: default ignore rules', pp)
        return
    if any(fnmatch(str(pp), o) for o in opts.ignored):
        logger.debug('ignoring %s: user ignore rules', pp)
        return

    if pp.is_dir():
        paths = list(pp.glob('*')) # meh
        for p in paths:
            yield from _index(p, opts=opts)
        return

    if pp.is_symlink():
        if opts.follow:
            yield from _index(pp.resolve(), opts=opts)
        else:
            logger.debug('ignoring symlink %s', pp)
        return

    try:
        yield from _index_file(pp, opts=opts)
    except Exception as e:
        # quite likely due to unavoidable race conditions
        yield e


def _index_file(pp: Path, opts: Options) -> Iterator[Extraction]:
    logger = get_logger()
    # TODO use kompress?
    # TODO not even sure if it's used...
    suf = pp.suffix.lower()

    if suf == '.xz':
        import lzma
        uname = pp.name[:-len('.xz')]
        uncomp = Path(get_tmpdir().name) / uname
        with lzma.open(pp, 'rb') as cf:
            with uncomp.open('wb') as fb:
                fb.write(cf.read())
        yield from _index(path=uncomp, opts=opts)
        return

    # TODO dispatch org mode here?
    # TODO try/catch?

    if suf not in SMAP:
        pm = mime(pp)
        if pm not in SMAP:
            yield RuntimeError(f"Unexpected file extension: {pp}, {pm}")
            return
        else:
            ip = SMAP.get(pm, None)
        # TODO assume plaintext?
    else:
        ip = SMAP.get(suf, None)
    if ip is None:
        # TODO only log once?
        logger.debug('file type suppressed: %s', pp)
        return

    indexer: Union[Urls, Iterator[Extraction]] = ip(pp) # type: ignore
    # TODO careful, filter out obviously not plaintext? maybe mime could help here??

    fallback_dt = datetime.fromtimestamp(pp.stat().st_mtime, tz=pytz.utc)
    loc = Loc.file(pp)
    for r in indexer:
        if isinstance(r, EUrl):
            yield Visit(
                url=r.url,
                dt=fallback_dt,
                locator=loc,
                context='::'.join(r.ctx),
            )
        else:
            yield r
