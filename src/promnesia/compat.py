from typing import TYPE_CHECKING

if not TYPE_CHECKING:
    ## we used to have compat fixes here for these for python3.7
    ## keeping in case any sources depended on compat functions
    from subprocess import PIPE, Popen, check_call, check_output, run  # noqa: F401
    from typing import Literal, Protocol  # noqa: F401
    ##

    # todo deprecate properly
    def removeprefix(text: str, prefix: str) -> str:
        return text.removeprefix(prefix)
