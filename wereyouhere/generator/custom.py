from datetime import datetime
from subprocess import check_output, check_call

from wereyouhere.common import Entry, History

def get_custom_history(command: str) -> History:
    output = check_output(command, shell=True)
    urls = [line.decode('utf-8') for line in output.splitlines()]
    history: History = {}
    for u in urls:
        history[u] = Entry(url=u, visits={datetime.now()}) # TODO mm, use something a bit more meaningful..
    return history
