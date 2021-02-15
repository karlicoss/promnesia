from datetime import datetime
import re
from subprocess import check_call, check_output
from typing import Optional
from urllib.parse import unquote

from ..common import Visit, Loc, Results, extract_urls, file_mtime, get_system_tz, now_tz, _is_windows


def index(command: str) -> Results:
    tz = get_system_tz()

    def handle_line(line: str) -> Results:
        # grep dumps this as
        # /path/to/file:lineno:rest
        # note: on Windows, path contains :...
        m = re.search(r'(.*):(\d+):(.*)', line)
        if m is None:
            # todo warn maybe?
            fname = None
            lineno = None
        else:
            fname  = m.group(1)
            lineno = int(m.group(2))
            line   = m.group(3)

        urls = extract_urls(line)
        if len(urls) == 0:
            return

        context = line

        ts: datetime
        loc: Loc
        if fname is not None:
            ts = file_mtime(fname)
            loc = Loc.file(fname, line=lineno)
        else:
            ts = now_tz()
            loc = Loc.make(command)
        for url in urls:
            yield Visit(
                url=url,
                dt=ts,
                locator=loc,
                context=context,
            )

    # FIXME remove shell=True...
    output = check_output(command, shell=True)
    lines = [line.decode('utf-8') for line in output.splitlines()]
    for line in lines:
        try:
            yield from handle_line(line)
        except Exception as e:
            yield e
