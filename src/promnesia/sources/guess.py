# TODO eh. confusing how guess and auto are different...
# maybe merge them later?
from typing import Iterable, Any

from ..common import Extraction, PathIsh


def is_git_repo(p: str) -> bool:
    if '://github.com/' in p:
        return True
    return False


def is_website(p: str) -> bool:
    if p.startswith('http'):
        return True
    return False


def index(path: PathIsh, *args, **kwargs) -> Iterable[Extraction]:
    ps = str(path)
    # TODO better url detection

    index_: Any # meh
    if is_git_repo(ps):
        from . import vcs
        index_ = vcs.index
    elif is_website(ps):
        from . import website
        index_ = website.index
    else:
        from . import auto
        index_ = auto.index
    yield from index_(path, *args, **kwargs)
