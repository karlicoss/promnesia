import csv
from datetime import datetime
from subprocess import check_output
from typing import List, Dict, Set, NamedTuple, Iterator

from wereyouhere.common import Entry, merge_histories, History

def iter_chrome_history_files(where: str) -> Iterator[str]:
    """
    Collects all sqlite chrome history files in the directory
    """
    from os.path import join, isdir
    from os import walk

    import magic # type: ignore
    mime = magic.Magic(mime=True)
    for root, dirs, files in walk(where):
        for f in files:
            full = join(root, f)
            m = mime.from_file(full)
            if m == 'application/x-sqlite3':
                yield full

def read_chrome_history(histfile: str) -> History:
    out = check_output(f"""sqlite3 -csv '{histfile}' 'SELECT datetime(((visits.visit_time/1000000)-11644473600), "unixepoch"), urls.url, urls.title FROM urls, visits WHERE urls.id = visits.url;'""", shell=True).decode('utf-8')
    urls: History = {}
    for x in csv.DictReader(out.splitlines(), fieldnames=['time', 'url', 'title']):
        # TODO normalise!
        url = x['url']
        e = urls.get(url, None)
        if e is None:
            e = Entry(url=url, visits=set())
        e.visits.add(x['time']) # TODO collapse temporaly close entries??
        urls[url] = e
    return urls

def iter_chrome_histories(where: str):
    for hfile in iter_chrome_history_files(where):
        yield read_chrome_history(hfile)
