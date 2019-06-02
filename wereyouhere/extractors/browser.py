import csv
from datetime import datetime
from subprocess import check_output
from typing import List, Dict, Set, NamedTuple, Iterator
import pytz
from urllib.parse import unquote
import sqlite3

from wereyouhere.common import PathIsh, PreVisit, get_logger, Loc

from sqlalchemy import create_engine, MetaData # type: ignore
from sqlalchemy import Column, Table # type: ignore

def browser_extract(histfile: PathIsh, tag: str, cols, row_handler) -> Iterator[PreVisit]:
    logger = get_logger()
    logger.debug(f'extracing history from {histfile}')

    # TODO fuck. why doesn't that work???
    # engine = create_engine('sqlite:///{histfile}', echo=True)
    # meta = MetaData()
    # visits = Table('visits', meta, autoload=True, autoload_with=engine)
    conn = sqlite3.connect(str(histfile))

    for row in conn.execute(f"SELECT {', '.join(cols)} FROM visits"):
        pv = row_handler(*row)
        yield pv

    logger.debug('done extracing')


def _firefox(cols, histfile: PathIsh, tag: str) -> Iterator[PreVisit]:
    def row_handler(url, ts):
        # ok, looks like it's unix epoch
        # https://stackoverflow.com/a/19430099/706389
        dt = datetime.fromtimestamp(int(ts) / 1_000_000, pytz.utc)
        url = unquote(url) # firefox urls are all quoted
        return PreVisit(
            url=url,
            dt=dt,
            tag=tag,
            locator=Loc.make(histfile),
        )
    yield from browser_extract(
        histfile=histfile,
        tag=tag,
        cols=cols,
        row_handler=row_handler,
    )

def firefox_phone(histfile: PathIsh, tag: str='firefox') -> Iterator[PreVisit]:
    yield from _firefox(cols=('url', 'date'), histfile=histfile, tag=tag)

def firefox(histfile: PathIsh, tag: str='firefox') -> Iterator[PreVisit]:
    yield from _firefox(cols=('url', 'visit_date'), histfile=histfile, tag=tag)


# should be utc? https://stackoverflow.com/a/26226771/706389
# yep, tested it and looks like utc
def chrome_time_to_utc(chrome_time: int) -> datetime:
    epoch = (chrome_time / 1_000_000) - 11644473600
    return datetime.fromtimestamp(epoch, pytz.utc)


# TODO could use sqlite3 module I guess... but it's quick enough to extract as it is
def chrome(histfile: PathIsh, tag: str='chrome') -> Iterator[PreVisit]:
    def row_handler(url, ts):
        dt = chrome_time_to_utc(int(ts))
        url = unquote(url) # chrome urls are all quoted
        return PreVisit(
            url=url,
            dt=dt,
            tag=tag,
            locator=Loc.make(histfile),
        )

    yield from browser_extract(
        histfile=histfile,
        tag=tag,
        cols=('url', 'visit_time'),
        row_handler=row_handler,
    )
