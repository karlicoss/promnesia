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
    # TODO hmm, this up doesn't save channel handles in database??
    # TODO sender id is always user?
    # ok, that would make a little more sense
    """
    SELECT S.display_name
        , M.time
        , M.text
        , M.id
    FROM messages AS M
    LEFT JOIN (
    SELECT type, id, coalesce(username, id) as handle, coalesce(first_name || " " || last_name, username, id) as display_name FROM users
    UNION
    SELECT type, id, id as handle                    , coalesce(name, id) as display_name FROM chats
    ) as S
    ON /* M.source_type = S.type AND */ M.source_id = S.id
    WHERE (text like '%zdx4%') ORDER BY S.display_name;
    """

    query = """
SELECT coalesce(U.first_name || " " || U.last_name, U.username) AS sender
     , coalesce(C.first_name || " " || C.last_name, C.username) AS chatname
     , C.username as chat
     , M.time AS time
     , M.text AS text
     , M.id AS mid
FROM messages AS M
JOIN users AS U ON U.id == M.sender_id
JOIN users AS C ON C.id == M.source_id
WHERE has_media == 1 or (text like '%http%');
    """.strip()
    for row in db.query(query):
        text = row['text']
        urls = extract_urls(text)
        if len(urls) == 0:
            continue
        sender   = row['sender']
        chatname = row['chatname']
        dt = from_epoch(row['time'])

        chat     = row['chat']
        mid      = row['mid']
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
                tag=tag,
            )
