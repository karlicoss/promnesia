from datetime import datetime
from os import stat
from subprocess import check_output, check_call
from typing import Optional, Iterable
from urllib.parse import unquote
from pathlib import Path

import csv
import json

import pytz

from wereyouhere.common import PreVisit, Tag, Url, PathIsh, get_logger, Loc, get_tmpdir, extract_urls


def extract(command: str, tag: Tag) -> Iterable[PreVisit]:
    output = check_output(command, shell=True)
    lines = [line.decode('utf-8') for line in output.splitlines()]
    for line in lines:
        protocols = ['file', 'ftp', 'http', 'https']
        for p in protocols:
            split_by = ':' + p + '://'
            if split_by in line:
                parts = line.split(split_by)
                break
        else:
            parts = [line]

        fname: Optional[str]
        lineno: Optional[str]
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
        if fname:
            ts = datetime.fromtimestamp(stat(fname).st_mtime)
        else:
            ts = datetime.utcnow().replace(tzinfo=pytz.utc)
        # TODO !1 extract org notes properly...
        yield PreVisit(
            url=url,
            dt=ts,
            tag=tag,
            locator=Loc.make(fname, line=lineno),
            context=context,
        )

from typing import List
def _collect(thing, result: List[Url]):
    if isinstance(thing, str):
        result.extend(extract_urls(thing))
    elif isinstance(thing, list):
        for x in thing:
            _collect(x, result)
    elif isinstance(thing, dict):
        for k, v in thing.items():
            _collect(k, result)
            _collect(v, result)
    else:
        pass

from typing import Union
from tempfile import TemporaryDirectory


# TODO FIXME unquote is temporary hack till we figure out everything..
def simple(path: Union[List[PathIsh], PathIsh], tag: Tag, do_unquote=False) -> Iterable[PreVisit]:
    logger = get_logger()
    if isinstance(path, list):
        for p in path:
            yield from simple(p, tag=tag)
        return

    pp = Path(path)
    urls: List[Url] = []
    # TODO ugh. kythonize that..
    if pp.suffix == '.xz':
        import lzma
        uname = pp.name[:-len('.xz')]
        uncomp = Path(get_tmpdir().name) / uname
        with lzma.open(pp, 'rb') as cf:
            with uncomp.open('wb') as fo:
                fo.write(cf.read())
        yield from simple(path=uncomp, tag=tag, do_unquote=True) # ugh. only used for reddit currelty
    elif pp.suffix == '.json': # TODO make it possible to force
        jj = json.loads(pp.read_text())
        uuu: List[str] = []
        _collect(jj, uuu)
        if do_unquote:
            uuu = [unquote(u) for u in uuu]
        urls.extend(uuu)
    elif pp.suffix == '.csv':
        with pp.open() as fo:
            reader = csv.DictReader(fo)
            for line in reader:
                _collect(line, urls)
    else:
        # TODO use url extractor..
        logger.info(f'{pp}: fallback to grep')
        from wereyouhere.generator.plaintext import extract_from_path
        yield from extract(extract_from_path(pp), tag=tag)
        # raise RuntimeError(f'Unexpected suffix {pp}')

    dt = datetime.fromtimestamp(pp.stat().st_mtime, tz=pytz.utc)

    for u in urls:
        yield PreVisit(
            url=u,
            dt=dt,
            tag=tag,
            locator=Loc.make(pp),
        )

