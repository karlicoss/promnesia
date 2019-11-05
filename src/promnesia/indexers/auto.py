import csv
from datetime import datetime
import json
from typing import Optional, Iterable, Union, List, Tuple, NamedTuple, Sequence, Iterator
from pathlib import Path
from urllib.parse import unquote

import pytz

from ..common import Visit, Url, PathIsh, get_logger, Loc, get_tmpdir, extract_urls


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


Urls = Iterator[Url]

def _csv(path: Path) -> Urls:
    # TODO these could also have Loc to be fair..
    with path.open() as fo:
        # TODO shit need to urldecode
        reader = csv.DictReader(fo)
        for line in reader:
            yield from urls.extend(collect_from(line))

def _json(path: Path) -> Urls:
    jj = json.loads(path.read_text())
    yield from collect_from(jj)

def _plaintext(path: Path) -> Urls:
    from . import shellcmd
    yield from shellcmd.extract()
    pass


def _markdown(path: Path) -> Urls:
    # TODO for now handled as plaintext
    yield from _plaintext(path)


SMAP = {
    'json'       : _json,
    'csv'        : _csv,

    # 'org'        : TODO,
    # 'org_archive': TODO,

    'md'         : _markdown,
    'markdown'   : _markdown,


    # TODO compressed?
}
# TODO ok, mime doesn't really tell between org/markdown/etc anyway


# TODO FIXME unquote is temporary hack till we figure out everything..
# TODO extraction?
def simple(path: Union[List[PathIsh], PathIsh], do_unquote=False) -> Iterable[Visit]:
    logger = get_logger()
    if isinstance(path, list):
        # TODO mm. just walk instead??
        for p in path:
            yield from simple(p)
        return

    pp = Path(path)
    # TODO use kompress?
    # TODO not even sure if it's used...
    if pp.suffix == '.xz':
        import lzma
        uname = pp.name[:-len('.xz')]
        uncomp = Path(get_tmpdir().name) / uname
        with lzma.open(pp, 'rb') as cf:
            with uncomp.open('wb') as fb:
                fb.write(cf.read())
        yield from simple(path=uncomp, do_unquote=do_unquote)
        return

    suf = pp.suffix

    SMAP[suf]
    # TODO careful, filter out obviously not plaintext? maybe mime could help here??

    urls: List[EUrl]
        # TODO use url extractor..
        logger.info(f'{pp}: fallback to grep')
        from .plaintext import extract_from_path
        yield from extract(extract_from_path(pp))
        # raise RuntimeError(f'Unexpected suffix {pp}')
        return

    dt = datetime.fromtimestamp(pp.stat().st_mtime, tz=pytz.utc)

    for eu in urls:
        yield Visit(
            url=eu.url, # TODO FIXME use ctx?
            dt=dt,
            locator=Loc.file(pp),
        )

