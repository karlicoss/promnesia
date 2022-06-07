'''
Clones & indexes Git repositories (via sources.auto)
'''
# TODO not sure if worth exposing... could be just handled by auto or something?)

from pathlib import Path
import re
from typing import Iterable

from ..common import Extraction, PathIsh, get_tmpdir, slugify
from ..compat import check_call


def index(path: PathIsh, *args, **kwargs) -> Iterable[Extraction]:
    repo = str(path)

    # TODO this looks pretty horrible as a context name
    # perhaps pass context here since we know it should be github repo?
    tp = Path(get_tmpdir().name) / slugify(repo)
    # note: https://bugs.python.org/issue33617 , it doesn't like Path here on Windows
    check_call(['git', 'clone', repo, str(tp)])

    def replacer(p: PathIsh, prefix: str=str(tp), repo: str=repo) -> str:
        ps = str(p)
        # TODO prefix is a bit misleading
        pos = ps.find(prefix)
        if pos == -1:
            # TODO not sure if should happen...
            return ps
        # TODO ugh. seems that blame view https://github.com/davidgasquez/handbook/blame/master/README.md#L25 is the most reliable
        # in raw mode can't jump onto line, when markdown is renderend can't jump either
        rest = ps[pos + len(prefix):]
        rest = re.sub(r':(\d+)$', r'#L\1', rest) # patch line number...
        return repo + '/blame/master' + rest

        # TODO doesn't work for git:
        # TODO think about something more generic... this isn't too sustainable
    # TODO not sure if context should be local or github?...

    from . import auto
    yield from auto.index(tp, *args, replacer=replacer, **kwargs)
