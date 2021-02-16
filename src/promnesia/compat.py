from pathlib import Path
from typing import Union, Sequence, List, TYPE_CHECKING

PathIsh = Union[Path, str]


Paths = Sequence[PathIsh]

# TLDR: py37 on windows has an annoying bug.. https://github.com/karlicoss/promnesia/issues/91#issuecomment-701051074
def _fix(args: Paths) -> List[str]:
    return list(map(str, args))

import subprocess

def run(args: Paths, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(_fix(args), **kwargs)

def check_call(args: Paths, **kwargs) -> None:
    subprocess.check_call(_fix(args), **kwargs)
    
def check_output(args: Paths, **kwargs) -> bytes:
    return subprocess.check_output(_fix(args), **kwargs)
    
def Popen(args: Paths, **kwargs) -> subprocess.Popen:
    return subprocess.Popen(_fix(args), **kwargs)

PIPE = subprocess.PIPE
