from pathlib import Path

from wereyouhere.common import PathIsh

def get_last_new(ddd: PathIsh, glob: str) -> Path:
    p = Path(ddd)
    return max(p.glob(glob))
