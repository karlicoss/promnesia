import csv
from datetime import datetime
from subprocess import check_output
from typing import List, Dict, Set, NamedTuple, Iterator
from urllib.parse import unquote

import pytz

from wereyouhere.common import PathIsh, PreVisit, get_logger

def extract(histfile: PathIsh, tag: str='chrome') -> Iterator[PreVisit]:
    logger = get_logger()

    # TODO could use sqlite3 module I guess... but it's quick enough to extract as it is
    logger.debug(f'extracing history from {histfile}')
    out = check_output(f"""sqlite3 -csv '{str(histfile)}' 'SELECT visits.visit_time, urls.url FROM urls, visits WHERE urls.id = visits.url;'""", shell=True).decode('utf-8')
    logger.debug('done reading')
    for ts, url in csv.reader(out.splitlines()):
        # TODO hmm, not so sure about this unquote...
        url = unquote(url)

        # should be utc? https://stackoverflow.com/a/26226771/706389
        # yep, tested it and looks like utc
        epoch = (int(ts) / 1_000_000) - 11644473600
        dt = datetime.utcfromtimestamp(epoch).replace(tzinfo=pytz.utc)

        yield PreVisit(
            url=url,
            dt=dt,
            tag=tag,
        )
    logger.debug('done extracing')
