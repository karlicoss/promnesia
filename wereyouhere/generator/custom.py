from datetime import datetime
from subprocess import check_output, check_call

from wereyouhere.common import Entry, History, Visit

def get_custom_history(command: str, tag: str = "") -> History:
    output = check_output(command, shell=True)
    urls = [line.decode('utf-8') for line in output.splitlines()]
    history = History()
    for url in urls:
        visit = Visit(dt=datetime.now(), tag=tag)
        history.register(url, visit)
    return history
