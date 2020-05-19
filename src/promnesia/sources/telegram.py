'''
Uses [[https://github.com/fabianonline/telegram_backup#readme][telegram_backup]] database for messages data
'''

from pathlib import Path
from typing import Optional, Union, TypeVar
from urllib.parse import unquote # TODO mm, make it easier to rememember to use...

import dataset # type: ignore

from ..common import PathIsh, Visit, get_logger, Loc, extract_urls, from_epoch, Results, echain

# TODO potentially, belongs to my. package

# TODO kython?
T = TypeVar('T')
def unwrap(res: Union[T, Exception]) -> T:
    if isinstance(res, Exception):
        raise res
    else:
        return res


# TODO move to common?
def dataset_readonly(db: Path):
    # see https://github.com/pudo/dataset/issues/136#issuecomment-128693122
    import sqlite3
    creator = lambda: sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    return dataset.connect('sqlite:///' , engine_kwargs={'creator': creator})


def index(database: PathIsh) -> Results:
    logger = get_logger()

    path = Path(database)
    assert path.is_file()

    # TODO context manager?
    db = dataset_readonly(path)

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
                                                                    /* chat types are 'dialog' (1-1), 'group' and 'supergroup' */
                                                                    /* this is abit hacky way to handle all groups in one go */
LEFT JOIN entities AS src    ON M.source_id = src.id AND src.type = (CASE M.source_type WHEN 'supergroup' THEN 'group' ELSE M.source_type END)
LEFT JOIN entities AS snd    ON M.sender_id = snd.id AND snd.type = 'dialog'
WHERE
    M.message_type NOT IN ('service_message', 'empty_message')
/* used to do this, but doesn't really give much of a speedup */
/* AND (M.has_media == 1 OR (text LIKE '%http%')) */
ORDER BY time;
    """.strip()

    # TODO yield error if chatname or chat or smth else is null?
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


def _handle_row(row) -> Results:
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
        yield Visit(
            url=unquote(u),
            dt=dt,
            context=f"{sender}: {text}",
            locator=Loc.make(
                title=f"chat with {chatname}",
                href=in_context,
            ),
        )
