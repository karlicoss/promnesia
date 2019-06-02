from datetime import datetime
from os import stat
from subprocess import check_output, check_call
from typing import Optional, Iterable, Union, List, Tuple, NamedTuple
from urllib.parse import unquote
from pathlib import Path
from tempfile import TemporaryDirectory

import csv
import json

import pytz

from wereyouhere.common import PreVisit, Tag, Url, PathIsh, get_logger, Loc, get_tmpdir, extract_urls


def extract(command: str, tag: Tag) -> Iterable[PreVisit]:
    output = check_output(command, shell=True)
    lines = [line.decode('utf-8') for line in output.splitlines()]
    for line in lines:
        # TODO wtf is that??? use extract_url??
        protocols = ['file', 'ftp', 'http', 'https']
        for p in protocols:
            split_by = ':' + p + '://'
            if split_by in line:
                parts = line.split(split_by)
                break
        else:
            parts = [line]

        fname: Optional[str]
        lineno: Optional[int]
        url: str
        if len(parts) == 1:
            fname = None
            lineno = None
            url = parts[0]
        else:
            [fname, lineno] = parts[0].rsplit(':', maxsplit=1)
            lineno = int(lineno) # type: ignore
            url = split_by[1:] + parts[1]

        context = f"{fname}:{lineno}" if fname and lineno else None

        url = unquote(url)

        ts: datetime
        loc: Loc
        if fname is not None:
            ts = datetime.fromtimestamp(stat(fname).st_mtime)
            loc = Loc.file(fname, line=lineno)
        else:
            ts = datetime.utcnow().replace(tzinfo=pytz.utc)
            loc = Loc.make(command)
        # TODO !1 extract org notes properly...
        yield PreVisit(
            url=url,
            dt=ts,
            tag=tag,
            locator=loc,
            context=context,
        )

Ctx = Tuple[str]

class EUrl(NamedTuple):
    url: Url
    ctx: Ctx



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

def collect_from(thing) -> List[EUrl]:
    uuu: List[EUrl] = []
    path: List[str] = []
    _collect(thing, path, uuu)
    return uuu



# TODO FIXME unquote is temporary hack till we figure out everything..
def simple(path: Union[List[PathIsh], PathIsh], tag: Tag, do_unquote=False) -> Iterable[PreVisit]:
    logger = get_logger()
    if isinstance(path, list):
        for p in path:
            yield from simple(p, tag=tag)
        return

    pp = Path(path)
    # TODO ugh. kythonize that..
    if pp.suffix == '.xz':
        import lzma
        uname = pp.name[:-len('.xz')]
        uncomp = Path(get_tmpdir().name) / uname
        with lzma.open(pp, 'rb') as cf:
            with uncomp.open('wb') as fo:
                fo.write(cf.read())
        yield from simple(path=uncomp, tag=tag, do_unquote=True) # ugh. only used for reddit currelty
        return

    urls: List[EUrl]
    if pp.suffix == '.json': # TODO make it possible to force
        jj = json.loads(pp.read_text())

        urls = collect_from(jj)
        if do_unquote:
            urls = [u._replace(url=unquote(u.url)) for u in urls]
    elif pp.suffix == '.csv':
        urls = []
        with pp.open() as fo:
            # TODO support do_unquote??
            # TODO shit need to urldecode
            reader = csv.DictReader(fo)
            for line in reader:
                urls.extend(collect_from(line))
    else:
        # TODO use url extractor..
        logger.info(f'{pp}: fallback to grep')
        from wereyouhere.generator.plaintext import extract_from_path
        yield from extract(extract_from_path(pp), tag=tag)
        # raise RuntimeError(f'Unexpected suffix {pp}')
        return

    dt = datetime.fromtimestamp(pp.stat().st_mtime, tz=pytz.utc)

    for eu in urls:
        yield PreVisit(
            url=eu.url, # TODO FIXME use ctx?
            dt=dt,
            tag=tag,
            locator=Loc.file(pp),
        )

