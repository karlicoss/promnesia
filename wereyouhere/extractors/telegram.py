from pathlib import Path
import json
import logging
from datetime import datetime
from typing import NamedTuple, List, Optional, Union, Iterable
from urllib.parse import unquote # TODO mm, make it easier to rememember to use...

from wereyouhere.common import PathIsh, PreVisit, get_logger, Loc, extract_urls, from_epoch

import dataset # type: ignore

# TODO tag??
def extract(database: PathIsh, tag: str) -> Iterable[PreVisit]:
    logger = get_logger()

    db = dataset.connect(f'sqlite:///{str(database)}')
    query = """
select coalesce(U.first_name || " " || U.last_name, U.username) as sender, M.time as time, M.text as text from messages as M JOIN users as U ON U.id == M.sender_id where has_media == 1 or (text like '%http%');
    """.strip()
    # TODO eh. filter out ntfy bot?
    for row in db.query(query):
        # TODO FIXME careful, check that extraction is reasonable..
        # TODO multiprocessing??
        text = row['text']
        urls = extract_urls(text) # TODO sort just in case? not sure..
        if len(urls) == 0:
            continue
        sender = row['sender']
        dt = from_epoch(row['time'])
        for u in urls:
            yield PreVisit(
                url=unquote(u),
                dt=dt,
                context=f"{sender}: {text}",
                locator=Loc.make(database), # TODO not sure if there is a better way... would be great to jump to the message though
                tag=tag,
            )
