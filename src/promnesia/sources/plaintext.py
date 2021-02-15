from ..common import get_logger, get_tmpdir, PathIsh, _is_windows

from pathlib import Path

from shlex import quote

# https://linux-and-mac-hacks.blogspot.co.uk/2013/04/use-grep-and-regular-expressions-to.html
_URL_REGEX = r'\b(https?|ftp|file)://[-A-Za-z0-9+&@#/%?=~_|!:,.;]*[-A-Za-z0-9+&@#/%=~_|]'

# -n to output line numbers so we could restore context
# -I to ignore binaries
# TODO on findows use 'find'?
# FIXME path should be escaped..
_GREP_CMD = r"""grep --color=never -E -I {grep_args} --exclude-dir=".git" '{regex}' {path} || true"""


def _extract_from_dir(path: str) -> str:
    if _is_windows:
        return fr'''findstr /S /P /N "https*://" "{path}\*"'''

    return _GREP_CMD.format(
        grep_args="-r -n",
        regex=_URL_REGEX,
        path=path, # TODO quote here too?
    )

def _extract_from_file(path: str) -> str:
    if _is_windows:
        # /P to skip non-printable
        # /N to print line number
        # /S to print filename
        return f'''findstr /S /P /N "https*://" "{path}"'''

    return _GREP_CMD.format(
        grep_args="-n",
        regex=_URL_REGEX,
        path=f"{quote(path)} /dev/null", # dev null to trick into displaying filename
    )

# TODO eh, misleading..
def extract_from_path(path: PathIsh) -> str:
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
