#!/usr/bin/env python3
from pathlib import Path
from typing import Dict, Callable, Optional, Sequence, NamedTuple, Union, Iterable

from ..common import Results, Url


# TODO doesn't really belong here...
Ctx = Sequence[str]

class EUrl(NamedTuple):
    url: Url
    ctx: Ctx # TODO ctx here is more like a Loc
###


# keys are mime types + extensions
Ex = Callable[[Path], Union[Results, Iterable[EUrl]]]
# None means unhandled
MAPPING: Dict[str, Optional[Ex]] = {}
# NOTE: there are some types in auto.py at the moment... it's a bit messy


# for now source code just indexed with grep, not sure if it's good enough?
# if not, some fanceir library could be used...
# e.g. https://github.com/karlicoss/promnesia/pull/152/commits/c2f00eb4ee4018b02c9bf3966a036db69a43373d

# TODO use this list?
# https://github.com/GerritCodeReview/gerrit/blob/master/resources/com/google/gerrit/server/mime/mime-types.properties
CODE = {
    'text/x-python'     ,
    'text/x-tex'        ,
    'text/x-lisp'       ,
    'text/x-shellscript',
    'text/x-java'       ,
    'text/troff'        ,
    'text/x-c'          ,
    'text/x-c++'        ,
    'text/x-makefile'   ,
    'text/x-asm'        ,

    # FIXME dot
    'tex',
    'css',
    'sh' ,
    'js' ,
    'hs' ,
    'bat',
    'pl' ,
    'h'  ,
    'rs' ,
    'py' ,
}
# TODO discover more extensions with mimetypes library?


BINARY = '''
application/x-sqlite3
application/x-archive
application/x-pie-executable
.o
image/jpeg
.jpg
.png
image/png
.gif
.svg
.ico
inode/x-empty
.class
.jar
# comment
.mp3
.mp4
webm
'''

for x in BINARY.splitlines():
    x = x.strip()
    if len(x) == 0 or x[0] == '#':
        continue
    MAPPING[x] = lambda *args: () # just return empty sequence # TODO log?


handle_later = lambda *args, **kwars: ()


MAPPING.update({
    # TODO not sure about these:
    'text/xml': None,

    # TODO def could extract from source code...

    # TODO possible in theory?
    '.ppt' : None,
    '.pptx': None,
    '.xlsx': None,
    '.doc' : None,
    '.docx': None,
    '.ods' : None,
    '.odt' : None,
    '.rtf' : None,
    '.epub': None,
    '.pdf' : None,
    '.vcf' : None,
    '.djvu': None,
    '.dvi' : None,
    'application/msword': None,
    'application/postscript': None,
    'message/rfc822': None,

    # TODO not sure what to do about these..
    'application/octet-stream': handle_later,
    'application/zip'         : handle_later,
    'application/x-tar'       : handle_later,
    'application/gzip'        : handle_later,
})


# TODO use some existing file for initial gitignore..
IGNORE = [
    '.idea',
    'venv',
    '.git',
    '.mypy_cache',
    '.pytest_cache',
    'node_modules',
    '__pycache__',
    '.tox',
    '.stack-work',
    # TODO use ripgrep?

    # TODO not sure about these:
    '.gitignore',
    '.babelrc',
]
