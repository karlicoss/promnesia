from __future__ import annotations

from collections.abc import Iterable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Callable, NamedTuple, Union

from ..common import Results, Url

# TODO doesn't really belong here...
Ctx = Sequence[str]


class EUrl(NamedTuple):
    url: Url
    ctx: Ctx  # TODO ctx here is more like a Loc


###


# keys are mime types + extensions
Ex = Callable[[Path], Union[Results, Iterable[EUrl]]]
# None means unhandled
TYPE2IDX: dict[str, Ex | None] = {}
# NOTE: there are some types in auto.py at the moment... it's a bit messy


# TYPE2IDX only contains the 'prefixes', to speed up the lookup we are using cache..
@lru_cache(None)
def type2idx(t: str) -> Ex | None:
    if len(t) == 0:
        return None  # just in case?
    # first try exact match
    e = TYPE2IDX.get(t, None)
    if e is not None:
        return e
    t = t.strip('.')
    e = TYPE2IDX.get(t, None)
    if e is not None:
        return e
    # otherwise, try prefixes?
    for k, v in TYPE2IDX.items():
        if t.strip('.').startswith(k):
            return v
    return None


# for now source code just indexed with grep, not sure if it's good enough?
# if not, some fanceir library could be used...
# e.g. https://github.com/karlicoss/promnesia/pull/152/commits/c2f00eb4ee4018b02c9bf3966a036db69a43373d

# TODO use this list?
# https://github.com/GerritCodeReview/gerrit/blob/master/resources/com/google/gerrit/server/mime/mime-types.properties
# later these might do something clever, e.g. stripping off code comments etc?
CODE = {
    'text/x-java',
    'text/x-tex',
    'text/x-sh',
    'text/x-haskell',
    'text/x-perl',
    'text/x-python', 'text/x-script.python',
    'text/x-chdr',
    'text/x-csrc',
    'text/x-c',
    'text/x-c++',
    'text/x-makefile',
    'text/troff',
    'text/x-asm',
    'text/x-objective-c',
    'text/x-lisp',
    'text/vnd.graphviz',
    'text/x-diff',  # patch files
    'text/x-php',
    'text/x-lilypond',

    # these didn't have a mime type, or were mistyped?
    'css',
    'el',
    'rs',
    'go',
    'hs',  # mistyped on osx
    'hpp', # mistyped on osx

    'edn', # clojure data

    '.ts', # most likely typescript.. otherwise determined as text/vnd.trolltech.linguist mime
    '.js',
}  # fmt: skip
# TODO discover more extensions with mimetypes library?


BINARY = '''
# epub was failing to detect via mime on CI for some reason..
epub
inode/x-empty
.sqlite
# comment
application/
image/
audio/
video/
'''

handle_later = lambda *_args, **_kwargs: ()


def ignore(*_args, **_kwargs):
    # TODO log (once?)
    yield from ()


for x in BINARY.splitlines():
    x = x.strip()
    if len(x) == 0 or x[0] == '#':
        continue
    TYPE2IDX[x] = ignore


TYPE2IDX.update({
    '.xslx': ignore,
    '.vcf' : ignore,
    'message/rfc822': ignore, # ??

    # todo ignore all fonts?
    'font/woff2': ignore,
    'font/woff': ignore,
    'text/x-Algol68': ignore,  # ugh some license file had this?? maybe always index text/ as text?
    'text/x-bytecode.python': ignore,  # todo ignore all x-bytecode?
    'text/calendar': ignore,

    # TODO not sure what to do about these..
    'application/octet-stream': handle_later,
    'application/zip'         : handle_later,
    'application/x-tar'       : handle_later,
    'application/gzip'        : handle_later,
})  # fmt: skip


# TODO use some existing file for initial gitignore..
IGNORE = [
    '.idea',
    'venv',
    '.git',
    '.eggs',
    '.mypy_cache',
    '.pytest_cache',
    'node_modules',
    '__pycache__',
    '.tox',
    '.stack-work',

    # TODO not sure about these:
    '.gitignore',
    '.babelrc',
]  # fmt: skip
