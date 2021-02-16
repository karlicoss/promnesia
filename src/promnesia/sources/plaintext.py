from ..common import get_logger, get_tmpdir, PathIsh, _is_windows

from pathlib import Path
from typing import List

# https://linux-and-mac-hacks.blogspot.co.uk/2013/04/use-grep-and-regular-expressions-to.html
_URL_REGEX = r'\b(https?|ftp|file)://[-A-Za-z0-9+&@#/%?=~_|!:,.;]*[-A-Za-z0-9+&@#/%=~_|]'


# TODO hmm.. this might result in errors because grep exits with 1 if no matches were found... sigh
def _grep(*, paths: List[str], recursive: bool) -> List[str]:
    return [
        'grep',
        '--color=never',
        *(['-r'] if recursive else []),
        '-n', # print line numbers (to restore context)
        '-I', # ignore binaries
        '--exclude-dir=".git"',
        '-E', # 'extended' syntax
        _URL_REGEX,
        *paths,
    ]

def _findstr(*, path: str, recursive: bool) -> List[str]:
    return [
        'findstr',
        '/S',
        '/P',
        '/N',
        'https*://',
        path + (r'\*' if recursive else ''),
    ]


def _extract_from_dir(path: str) -> List[str]:
    if _is_windows:
        return _findstr(path=path, recursive=True)

    return _grep(
        paths=[path],
        recursive=True,
    )

def _extract_from_file(path: str) -> List[str]:
    if _is_windows:
        return _findstr(path=path, recursive=False)

    return _grep(
        paths=[path, '/dev/null'], # dev/null to trick into displaying filename
        recursive=False,
    )


def extract_from_path(path: PathIsh) -> List[str]:
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
