"""
Tries to index as much as it can:

- TODO walks up the filesystem hierarchy
- guesses org/markdown/json/etc by extension or mime type

"""

import csv
from datetime import datetime
import json
from typing import Optional, Iterable, Union, List, Tuple, NamedTuple, Sequence, Iterator
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
    logger.info(f'{path}: fallback to grep')
    yield from shellcmd.extract(extract_from_path(path))


def _markdown(path: Path) -> Iterator[Extraction]:
    # TODO for now handled as plaintext
    yield from _plaintext(path)


SMAP = {
    '.json'       : _json,
    '.csv'        : _csv,

    # 'org'        : TODO,
    # 'org_archive': TODO,

    '.md'         : _markdown,
    '.markdown'   : _markdown,

    'text/plain'  : _plaintext,
    '.txt'        : _plaintext,
    '.page'       : _plaintext,

    # TODO not sure about these:
    'text/x-python': None,
    'text/x-tex': None,
    'text/x-lisp': None,
    '.tex': None, # TODO not sure..
    '.css': None,
    '.sh' : None,

    # TODO compressed?
    '.jpg': None,
    '.png': None,
    '.gif': None,
    '.pdf': None,
    'inode/x-empty': None,
}
# TODO ok, mime doesn't really tell between org/markdown/etc anyway


# TODO FIXME unquote is temporary hack till we figure out everything..
def index(path: Union[List[PathIsh], PathIsh], do_unquote=False) -> Iterator[Extraction]:
    logger = get_logger()
    if isinstance(path, list):
        # TODO mm. just walk instead??
        for p in path:
            yield from index(p)
        return

    pp = Path(path)
    if not pp.is_file():
        logger.error('Expected file: %s', pp)
        # TODO FIXME walk dir
        return

    # TODO use kompress?
    # TODO not even sure if it's used...
    if pp.suffix == '.xz':
        import lzma
        uname = pp.name[:-len('.xz')]
        uncomp = Path(get_tmpdir().name) / uname
        with lzma.open(pp, 'rb') as cf:
            with uncomp.open('wb') as fb:
                fb.write(cf.read())
        yield from index(path=uncomp, do_unquote=do_unquote)
        return

    suf = pp.suffix
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
        logger.info(f'file type suppressed: {pp}')
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
