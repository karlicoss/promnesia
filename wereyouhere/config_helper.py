from pathlib import Path
from typing import Optional

from .common import PathIsh


def get_last(ddd: PathIsh, glob: Optional[str]=None) -> Path:
    p = Path(ddd)
    if glob is None:
        glob = '*'
    return max(p.glob(glob))
