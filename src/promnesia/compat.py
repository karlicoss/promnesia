## we used to have compat fixes here for these for python3.7
## keeping in case any sources depended on compat functions
from subprocess import PIPE, run, check_call, check_output, Popen
from typing import Protocol, Literal
## 


# can remove after python3.9
def removeprefix(text: str, prefix: str) -> str:
    if text.startswith(prefix):
        return text[len(prefix):]
    return text