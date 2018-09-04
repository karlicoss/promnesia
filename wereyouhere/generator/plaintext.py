import os.path

# https://linux-and-mac-hacks.blogspot.co.uk/2013/04/use-grep-and-regular-expressions-to.html
_URL_REGEX = r'\b(https?|ftp|file)://[-A-Za-z0-9+&@#/%?=~_|!:,.;]*[-A-Za-z0-9+&@#/%=~_|]'

# -n to output line numbers so we could restore context
# -I to ignore binaries
_GREP_CMD = r"""grep --color=never -Eo -I {grep_args} --exclude="*.html~" --exclude="*.html" --exclude-dir=".git" '{regex}' {path}"""


def _extract_from_dir(path: str) -> str:
    return _GREP_CMD.format(
        grep_args="-r -n",
        regex=_URL_REGEX,
        path=path,
    )

def _extract_from_file(path: str) -> str:
    return _GREP_CMD.format(
        grep_args="-n",
        regex=_URL_REGEX,
        path=f"'{path}' /dev/null", # dev null to trick into displaying filename
    )


def extract_from_path(path: str) -> str:
    if os.path.isdir(path):
        return _extract_from_dir(path)
    else:
        return _extract_from_file(path)
