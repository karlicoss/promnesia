from pathlib import Path
from subprocess import check_call
from typing import Iterable

from ..common import Extraction, PathIsh, get_tmpdir


def slugify(x: str) -> str:
    # https://stackoverflow.com/a/38766141/706389
    import re
    valid_file_name = re.sub(r'[^\w_.)( -]', '', x)
    return valid_file_name


def index(path: PathIsh, *args, **kwargs) -> Iterable[Extraction]:
    repo = str(path)

    # TODO this looks pretty horrible as a context name
    # perhaps pass context here since we know it should be github repo?
    tp = Path(get_tmpdir().name) / slugify(repo)
    check_call(['git', 'clone', repo, tp])

    from . import auto
    return auto.index(tp, *args, **kwargs)
