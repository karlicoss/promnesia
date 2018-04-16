from datetime import datetime
from subprocess import check_output, check_call

from wereyouhere.common import Entry, History, Visit

def get_custom_history(command: str, tag: str = "") -> History:
    output = check_output(command, shell=True)
    lines = [line.decode('utf-8') for line in output.splitlines()]
    history = History()
    for line in lines:
        parts = line.split(':http')
        context: str
        url: str
        if len(parts) == 1:
            url = parts[0]
            context = None
        else:
            [fname, lineno] = parts[0].rsplit(':', maxsplits=1)
            url = parts[1][len(':'):]
            context = f"{fname}:{lineno}"

        visit = Visit(
            dt=datetime.now(),
            tag=tag,
            context=context,
        )
        history.register(url, visit)
    return history
