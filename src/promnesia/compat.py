from pathlib import Path
from typing import Union, Sequence, List, TYPE_CHECKING

PathIsh = Union[Path, str]


Paths = Sequence[PathIsh]

# TLDR: py37 on windows has an annoying bug.. https://github.com/karlicoss/promnesia/issues/91#issuecomment-701051074
def _fix(args: Paths) -> List[str]:
    assert not isinstance(args, str), args # just to prevent shell=True calls...
    return list(map(str, args))


import argparse

def register_argparse_extend_action_in_pre_py38(parser: argparse.ArgumentParser):
    import sys

    if sys.version_info < (3, 8):

        class ExtendAction(argparse.Action):

            def __call__(self, parser, namespace, values, option_string=None):
                items = getattr(namespace, self.dest) or []
                items.extend(values)
                setattr(namespace, self.dest, items)


        parser.register('action', 'extend', ExtendAction)


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
