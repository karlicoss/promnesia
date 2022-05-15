from ..common import get_logger, get_tmpdir, PathIsh, _is_windows
from ..compat import removeprefix

from functools import lru_cache
from pathlib import Path
import os
from typing import List

# https://linux-and-mac-hacks.blogspot.co.uk/2013/04/use-grep-and-regular-expressions-to.html
_URL_REGEX = r'\b(https?|ftp|file)://[-A-Za-z0-9+&@#/%?=~_|!:,.;]*[-A-Za-z0-9+&@#/%=~_|]'

if _is_windows:
    # wtf? for some reason on windows (in cmd.exe specificaly) \b isn't working...
    # this will make the regex a bit less precise, but not end of the world
    _URL_REGEX = removeprefix(_URL_REGEX, r'\b')


@lru_cache()
def _has_grep() -> bool:
    import shutil
    return shutil.which('grep') is not None


Command = List[str]


_GREP_ARGS: Command = [
    '--color=never',
    '-H', # always show filename TODO not sure if works on osx
    '-n', # print line numbers (to restore context)
    '-I', # ignore binaries
]

if not _is_windows:
    # exclude-dir not working on windows
    _GREP_ARGS += [
        '--exclude-dir=".git"',
    ]

# NOTE: grep/findstr exit with code 1 on no matches...
# we hack around it in shellcmd module (search 'grep')
def _grep(*, paths: List[str], recursive: bool) -> Command:
    return [
        'grep',
        *(['-r'] if recursive else []),
        *_GREP_ARGS,
        '-E', # 'extended' syntax
        _URL_REGEX,
        *paths,
    ]

def _findstr(*, path: str, recursive: bool) -> Command:
    return [
        'findstr',
        '/S',
        '/P',
        '/N',
        'https*://',
        path + (r'\*' if recursive else ''),
    ]


# TODO unify these if it works??
def _extract_from_dir(path: str) -> Command:
    if _has_grep():
        return _grep(
            paths=[path],
            recursive=True,
        )
    elif _is_windows:
        return _findstr(path=path, recursive=True)
    else:
        raise RuntimeError("no grep; don't know which search tool to use!")


def _extract_from_file(path: str) -> Command:
    if _is_windows and not _has_grep():
        return _findstr(path=path, recursive=False)

    return _grep(
        paths=[path],
        recursive=False,
    )


def extract_from_path(path: PathIsh) -> Command:
    pp = Path(path)

    tdir = get_tmpdir()

    logger = get_logger()
    if pp.is_dir(): # TODO handle archives here???
        return _extract_from_dir(str(pp))
    else:
        if any(pp.suffix == ex for ex in (
                '.xz',
                '.bz2',
                '.gz',
                '.zip',
        )):
            logger.info(f"Extracting from compressed file {path}")
            raise RuntimeError(f"Archives aren't supported yet: {path}")
            import lzma
            from tempfile import NamedTemporaryFile
            # TODO hopefully, no collisions
            import os.path
            fname = os.path.join(tdir.name, os.path.basename(path))
            with open(fname, 'wb') as fo:
                with lzma.open(path, 'r') as cf:
                    fo.write(cf.read())
                return _extract_from_file(fname)
        else:
            r = _extract_from_file(str(pp))
            return r
