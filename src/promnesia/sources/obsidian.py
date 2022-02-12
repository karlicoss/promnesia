from pathlib import Path
from ..common import PathIsh

def obsidian_replacer(p: PathIsh) -> str:
    if isinstance(p, Path) or not p.startswith("editor://") or not p.endswith('.md'):
        return p
    
    path = p.split('/', 2)[-1]
    
    uri = f"obsidian://{path}"
    return uri
