from datetime import datetime
from os import stat
from subprocess import check_output, check_call
from typing import Optional, Iterable
from urllib.parse import unquote
from pathlib import Path

import pytz

from wereyouhere.common import PreVisit, Tag, Url, PathIsh


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
            context=context,
        )

from typing import List
def _collect(thing, result: List[Url]):
    if isinstance(thing, str):
        # TODO good enough?
        # or use regex?
        if thing.startswith('http'):
            result.append(thing)
    elif isinstance(thing, list):
        for x in thing:
            _collect(x, result)
    elif isinstance(thing, dict):
        for k, v in thing.items():
            _collect(k, result)
            _collect(v, result)
    else:
        pass

def simple(path: PathIsh, tag: Tag) -> Iterable[PreVisit]:
    pp = Path(path)
    urls: List[Url] = []
    if pp.suffix == '.json': # TODO make it possible to force
        import json
        jj = json.loads(pp.read_text())
        _collect(jj, urls)
    elif pp.suffix == '.csv':
        import csv
        with pp.open() as fo:
            reader = csv.DictReader(fo)
            for line in reader:
                _collect(line, urls)
    else:
        raise RuntimeError(f'Unexpected suffix {pp}')

    dt = datetime.fromtimestamp(pp.stat().st_mtime, tz=pytz.utc)

    for u in urls:
        yield PreVisit(
            url=u,
            dt=dt,
            tag=tag,
        )

