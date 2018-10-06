import csv
from datetime import datetime
from subprocess import check_output
from typing import List, Dict, Set, NamedTuple, Iterator
from urllib.parse import unquote

from wereyouhere.common import Entry, History, Visit

_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

def read_chrome_history(histfile: str, tag: str) -> History:
    out = check_output(f"""sqlite3 -csv '{histfile}' 'SELECT datetime(((visits.visit_time/1000000)-11644473600), "unixepoch"), urls.url, urls.title FROM urls, visits WHERE urls.id = visits.url;'""", shell=True).decode('utf-8')
    urls = History()
    for x in csv.DictReader(out.splitlines(), fieldnames=['time', 'url', 'title']):
        # TODO hmm, not so sure about this unquote...
        url = unquote(x['url']) 
        times = x['time']
        # TODO should be utc? https://stackoverflow.com/a/26226771/706389
        # yep, tested it and looks like utc
        time = datetime.strptime(times, _TIME_FORMAT)
        visit = Visit(
            dt=time,
            tag=tag,
        )
        urls.register(url, visit)
    return urls

def iter_chrome_histories(chrome_db: str, tag: str):
    import magic # type: ignore
    mime = magic.Magic(mime=True)
    m = mime.from_file(chrome_db)
    assert m == 'application/x-sqlite3'
    yield read_chrome_history(chrome_db, tag)
