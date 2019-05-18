import csv
from datetime import datetime
from subprocess import check_output
from typing import List, Dict, Set, NamedTuple, Iterator
import pytz
from urllib.parse import unquote

from wereyouhere.common import PathIsh, PreVisit, get_logger, Loc


def browser_extract(histfile: PathIsh, tag: str, cols, row_handler) -> Iterator[PreVisit]:
    logger = get_logger()

    # TODO could use sqlite3 module I guess... but it's quick enough to extract as it is
    logger.debug(f'extracing history from {histfile}')
    out = check_output(f"""sqlite3 -csv '{str(histfile)}' 'SELECT {', '.join(cols)} FROM visits;'""", shell=True).decode('utf-8')
    logger.debug('done reading')
    for url, ts in csv.reader(out.splitlines()):
        url, dt = row_handler(url, ts)
        # TODO hmm, not so sure about this unquote...
        url = unquote(url)

        yield PreVisit(
            url=url,
            dt=dt,
            tag=tag,
            locator=Loc.make(histfile),
        )
    logger.debug('done extracing')


def extract(histfile: PathIsh, tag: str='firefox') -> Iterator[PreVisit]:
    def row_handler(url, ts):
        # ok, looks like it's unix epoch
        # https://stackoverflow.com/a/19430099/706389
        dt = datetime.fromtimestamp(int(ts) / 1_000_000, pytz.utc)
        return (url, dt)
    yield from browser_extract(
        histfile=histfile,
        tag=tag,
        cols=('url', 'date'),
        row_handler=row_handler,
    )
