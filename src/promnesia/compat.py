from pathlib import Path
import sys
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
from subprocess import PIPE  # for convenience?


if TYPE_CHECKING:
    from subprocess import run, check_call, check_output, Popen
else:
    def run(args: Paths, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(_fix(args), **kwargs)

    def check_call(args: Paths, **kwargs) -> None:
        subprocess.check_call(_fix(args), **kwargs)

    def check_output(args: Paths, **kwargs) -> bytes:
        return subprocess.check_output(_fix(args), **kwargs)

    def Popen(args: Paths, **kwargs) -> subprocess.Popen:
        return subprocess.Popen(_fix(args), **kwargs)


# can remove after python3.9
def removeprefix(text: str, prefix: str) -> str:
    if text.startswith(prefix):
        return text[len(prefix):]
    return text


# TODO Deprecate instead, they shouldn't be exported form this module
# del PathIsh
# del Paths

if sys.version_info[:2] >= (3, 8):
    from typing import Protocol
else:
    if TYPE_CHECKING:
        from typing_extensions import Protocol  # type: ignore[misc]
    else:
        # todo could also use NamedTuple?
        Protocol = object
