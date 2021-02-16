from datetime import datetime
import re
from ..compat import check_output, Paths
from typing import Optional, Union
import warnings

from ..common import Visit, Loc, Results, extract_urls, file_mtime, get_system_tz, now_tz


def index(command: Union[str, Paths]) -> Results:
    cmd: Paths
    cmds: str
    if isinstance(command, str):
        cmds = command
        warnings.warn("Passing string as a command is very fragile('{command}'). Please use list instead.")
        cmd = command.split(' ')
    else:
        cmds = ' '.join(map(str, command))
        cmd = command

    tz = get_system_tz()

    def handle_line(line: str) -> Results:
        # grep dumps this as
        # /path/to/file:lineno:rest
        # note: on Windows, path contains : after the disk name..
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
            loc = Loc.make(cmds)
        for url in urls:
            yield Visit(
                url=url,
                dt=ts,
                locator=loc,
                context=context,
            )

    output = check_output(cmd)
    lines = [line.decode('utf-8') for line in output.splitlines()]
    for line in lines:
        try:
            yield from handle_line(line)
        except Exception as e:
            yield e
