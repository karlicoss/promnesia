from pathlib import Path
from .common import PathIsh, Visit, Source, last, Loc, Results, DbVisit, Context, Res


def root() -> Path:
    r = Path(__file__).absolute().parent.parent.parent
    assert (r / 'src').exists()
    return r
