from datetime import datetime
from subprocess import check_output, check_call
from urllib.parse import unquote
from os import stat

from wereyouhere.common import Entry, History, Visit

def get_custom_history(command: str, tag: str = "") -> History:
    output = check_output(command, shell=True)
    lines = [line.decode('utf-8') for line in output.splitlines()]
    history = History()
    for line in lines:
        split_by = ':http'
        parts = line.split(split_by) # TODO handle ftp, file etc here
        fname: str
        lineno: str
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
            ts = datetime.now()

        visit = Visit(
            dt=ts,
            tag=tag,
            context=context,
        )
        history.register(url, visit)
    return history
