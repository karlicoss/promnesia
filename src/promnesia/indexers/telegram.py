from pathlib import Path
import json
import logging
from datetime import datetime
from typing import NamedTuple, List, Optional, Union, Iterable
from urllib.parse import unquote # TODO mm, make it easier to rememember to use...

import dataset # type: ignore

from kython.kerror import echain, unwrap

from ..common import PathIsh, PreVisit, get_logger, Loc, extract_urls, from_epoch, Extraction



def extract(database: PathIsh) -> Iterable[Extraction]:
    logger = get_logger()

    # TODO context manager?
    db = dataset.connect(f'sqlite:///{str(database)}')

    def make_query(text_query: str):
        return f"""
WITH entities AS (
   SELECT 'dialog' as type, id, coalesce(username, id) as handle, coalesce(first_name || " " || last_name, username, id) as display_name FROM users
   UNION
   SELECT 'group' as type, id, id as handle                    , coalesce(name, id) as display_name FROM chats
)
SELECT src.display_name AS chatname
     , src.handle       AS chat
     , snd.display_name AS sender
     , M.time           AS time
     , {text_query}     AS text
     , M.id             AS mid
FROM messages AS M
LEFT JOIN entities AS src    ON M.source_type = src.type AND M.source_id = src.id
LEFT JOIN entities AS snd    ON 'dialog'      = snd.type AND M.sender_id = snd.id
WHERE
    M.message_type NOT IN ('service_message', 'empty_message')
/* used to do this, but doesn't really give much of a speedup */
/* AND (M.has_media == 1 OR (text LIKE '%http%')) */
ORDER BY time;
    """.strip()

    # TODO FIXME yield error if chatname or chat or smth else is null?
    for row in db.query(make_query('M.text')):
        try:
            yield from _handle_row(row)
        except Exception as ex:
            yield echain(RuntimeError(f'While handling {row}'), ex)
            # , None, sys.exc_info()[2]
            # TODO hmm. traceback isn't preserved; wonder if that's because it's too heavy to attach to every single exception object..

    # old (also 'stable') version doesn't have 'json' column yet...
    if 'json' in db['messages'].columns:
        for row in db.query(make_query("json_extract(json, '$.media.webpage.description')")):
            try:
                yield from _handle_row(row)
            except Exception as ex:
                yield echain(RuntimeError(f'While handling {row}'), ex)


def _handle_row(row) -> Iterable[Extraction]:
    text = row['text']
    if text is None:
        return
    urls = extract_urls(text)
    if len(urls) == 0:
        return
    dt            = from_epoch(row['time'])
    mid: str      = unwrap(row['mid'])

    # TODO perhaps we could be defensive with null sender/chat etc and still emit the Visit
    sender: str   = unwrap(row['sender'])
    chatname: str = unwrap(row['chatname'])
    chat: str     = unwrap(row['chat'])

    in_context = f'https://t.me/{chat}/{mid}'
    for u in urls:
        # https://www.reddit.com/r/Telegram/comments/6ufwi3/link_to_a_specific_message_in_a_channel_possible/
        # hmm, only seems to work on mobile app, but better than nothing...
        yield PreVisit(
            url=unquote(u),
            dt=dt,
            context=f"{sender}: {text}",
            locator=Loc.make(
                title=f"chat with {chatname}",
                href=in_context,
            ),
        )
