from datetime import datetime
from subprocess import check_call, check_output
from typing import Optional
from pathlib import Path
from urllib.parse import unquote

from ..common import Visit, Loc, Results, extract_urls, get_system_tz


def index(command: str) -> Results:
    tz = get_system_tz()

    def handle_line(line: str) -> Results:
        #
        # grep dumps this as
        # /path/to/file:lineno:rest
        fname: Optional[str]
        lineno: Optional[int]
        parts = line.split(':', maxsplit=2)
        url: str
        if len(parts) == 3:
            fname   = parts[0]
            lineno  = int(parts[1])
            line    = parts[2]
        else:
            fname = None
            lineno = None

        urls = extract_urls(line)
        if len(urls) == 0:
            return

        context = line

        ts: datetime
        loc: Loc
        if fname is not None:
            ts = datetime.fromtimestamp(Path(fname).stat().st_mtime, tz=tz)
            loc = Loc.file(fname, line=lineno)
        else:
            ts = datetime.now(tz=tz)
            loc = Loc.make(command)
        for url in urls:
            yield Visit(
                url=url,
                dt=ts,
                locator=loc,
                context=context,
            )

    output = check_output(command, shell=True)
    lines = [line.decode('utf-8') for line in output.splitlines()]
    for line in lines:
        try:
            yield from handle_line(line)
        except Exception as e:
            yield e
