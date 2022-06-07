from datetime import datetime
import os
import re
from typing import Optional, Union, Sequence
import warnings

from ..compat import run, PIPE
from ..common import Visit, Loc, Results, extract_urls, file_mtime, get_system_tz, now_tz, _is_windows, PathIsh
from .plaintext import _has_grep


def index(command: Union[str, Sequence[PathIsh]]) -> Results:
    cmd: Sequence[PathIsh]
    cmds: str
    if isinstance(command, str):
        cmds = command
        warnings.warn("Passing string as a command is very fragile('{command}'). Please use list instead.")
        cmd = command.split(' ')
    else:
        cmds = ' '.join(map(str, command))
        cmd = command

    tz = get_system_tz()

    # ugh... on windows grep does something nasty? e.g:
    # grep --color=never -r -H -n -I -E http 'D:\\a\\promnesia\\promnesia\\tests\\testdata\\custom'
    # D:\a\promnesia\promnesia\tests\testdata\custom/file1.txt:1:Right, so this points at http://google.com
    # so part of the path has fwd slashes, part has bwd slashes...
    needs_windows_grep_patching = _has_grep() and _is_windows

    def handle_line(line: str) -> Results:
        # grep dumps this as
        # /path/to/file:lineno:rest
        # note: on Windows, path contains : after the disk name..
        m = re.search(r'(.*?):(\d+?):(.*)', line)
        if m is None:
            # todo warn maybe?
            fname = None
            lineno = None
        else:
            fname  = m.group(1)
            lineno = int(m.group(2))
            line   = m.group(3)

        if fname is not None and needs_windows_grep_patching:
            fname = fname.replace('/', os.sep)

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

    r = run(cmd, stdout=PIPE)
    if r.returncode > 0:
        if not (cmd[0] in {'grep', 'findstr'} and r.returncode == 1): # ugh. grep returns 1 on no matches...
            r.check_returncode()
    output = r.stdout
    assert output is not None
    lines = [line.decode('utf-8') for line in output.splitlines()]
    for line in lines:
        try:
            yield from handle_line(line)
        except Exception as e:
            yield e
