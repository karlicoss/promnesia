from datetime import datetime
from os import stat
from subprocess import check_output, check_call
from typing import Optional
from urllib.parse import unquote

import pytz

from wereyouhere.common import Entry, History, Visit


def get_custom_history(command: str, tag: str = "") -> History:
    output = check_output(command, shell=True)
    lines = [line.decode('utf-8') for line in output.splitlines()]
    history = History()
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
        visit = Visit(
            dt=ts,
            tag=tag,
            context=context,
        )
        history.register(url, visit)
    return history
