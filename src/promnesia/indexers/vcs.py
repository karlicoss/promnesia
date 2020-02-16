from pathlib import Path
from subprocess import check_call
from typing import Iterable

from ..common import Extraction, PathIsh, get_tmpdir, slugify


def index(path: PathIsh, *args, **kwargs) -> Iterable[Extraction]:
    repo = str(path)

    # TODO this looks pretty horrible as a context name
    # perhaps pass context here since we know it should be github repo?
    tp = Path(get_tmpdir().name) / slugify(repo)
    check_call(['git', 'clone', repo, tp])

    from . import auto
    yield from auto.index(tp, *args, **kwargs)
