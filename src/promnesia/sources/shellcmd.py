from datetime import datetime
from subprocess import check_call, check_output
from typing import Optional
from pathlib import Path
from urllib.parse import unquote

import pytz

from ..common import Visit, Loc, Results

def index(command: str) -> Results:
    output = check_output(command, shell=True)
    lines = [line.decode('utf-8') for line in output.splitlines()]
    # TODO eh?
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
            [fname, linenos] = parts[0].rsplit(':', maxsplit=1)
            lineno = int(linenos)
            url = split_by[1:] + parts[1]

        # TODO is it really necessary with locator?
        context = f"{fname}:{lineno}" if fname and lineno else None

        # TODO not sure if even necessary? not that I use canonify
        url = unquote(url)

        ts: datetime
        loc: Loc
        if fname is not None:
            ts = datetime.fromtimestamp(Path(fname).stat().st_mtime)
            loc = Loc.file(fname, line=lineno)
        else:
            # TODO fallback tz??
            ts = datetime.utcnow().replace(tzinfo=pytz.utc)
            loc = Loc.make(command)
        # TODO !1 extract org notes properly...
        yield Visit(
            url=url,
            dt=ts,
            locator=loc,
            context=context,
        )
