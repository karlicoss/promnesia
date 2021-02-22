"""
Adapted from `telegram.py` to read from `~/.ViberPC/XYZ123/viber.db`
"""

import json
import logging
import textwrap
from pathlib import Path
from typing import Optional, TypeVar, Union
from urllib.parse import \
    unquote  # TODO mm, make it easier to rememember to use...

from ..common import (Loc, PathIsh, Results, Visit, echain, extract_urls,
                      from_epoch, get_logger)

# TODO potentially, belongs to my. package

# TODO kython?
T = TypeVar("T")

logger = logging.getLogger(__name__)


def unwrap(res: Union[T, Exception]) -> T:
    if isinstance(res, Exception):
        raise res
    else:
        return res


# TODO move to common?
def dataset_readonly(db: Path):
    # see https://github.com/pudo/dataset/issues/136#issuecomment-128693122
    import sqlite3

    import dataset  # type: ignore

    creator = lambda: sqlite3.connect(f"file:{db}?immutable=1", uri=True)
    return dataset.connect("sqlite:///", engine_kwargs={"creator": creator})


def index(database: PathIsh) -> Results:
    is_debug = logger.isEnabledFor(logging.DEBUG)

    path = Path(database)
    assert path.is_file(), path

    # TODO context manager?
    db = dataset_readonly(path)  # TODO could check is_file inside

    query_str = textwrap.dedent(
        f"""
        /*
        Establish group-names by concatenating:
        - groups explicitely named,
        - multi-groups having a group-leader (PGRole=2), with
        - all the rest groups that (must) have just 2 members,
        me(ContactId=1) & "other" contact, so use this as group-name.
        */
        WITH G0 AS (
            SELECT
                CR.ChatId,
                CR.ContactID,
                coalesce(CI.Name, C.Name, C.ClientName) as chatname,
                CR.PGRole,
                CI.PGTags
            FROM ChatRelation as CR
            JOIN Contact AS C ON CR.ContactID = C.ContactID
            JOIN ChatInfo as CI ON CR.ChatId = CI.ChatId
        ), G1 AS (
            SELECT * FROM G0 WHERE PGRole = 2
        ), G2 AS (
            SELECT * FROM G0 WHERE
                ContactID <> 1 AND
                ChatId NOT IN (SELECT ChatId FROM G1)
        ), Groups AS (
            SELECT ChatId, chatname, PGTags FROM G1
            UNION
            SELECT ChatId, chatname, PGTags FROM G2
        )
        SELECT
            M.EventId           AS mid,
            E.TimeStamp         AS time,
            G.chatname          AS chatname,
            coalesce(
                S.Name,
                S.ClientName,
                '(' || S.Number || ')'          /* contacts have one xor the other, but failsafe */
            )                   AS sender,
            coalesce(M.Subject, M.Body)         /* didn't see any msg with both */    
                                AS text,
            M.info              AS infojson,    /* to harvested titles from embedded urls */
            G.PGTags            AS tags
        FROM messages AS M
        LEFT JOIN Events AS E
            ON M.EventId = E.EventId
        LEFT JOIN Contact AS S
            ON E.ContactId = S.ContactId
        LEFT JOIN Groups AS G
            ON E.ChatId = G.ChatId
        WHERE
            text LIKE '%http%'
        ORDER BY time;
        """
    )

    def _parse_json_title(js) -> str:
        if js and js.strip():
            js = json.loads(js)
            if isinstance(js, dict):
                return js.get("Title")

    def _handle_row(row) -> Results:
        text = row["text"]
        assert (
            text
        ), f"sql-query should have eliminated messages not containing 'http': {text}"
        urls = extract_urls(text)
        if not urls:
            return
        dt = from_epoch(row["time"] // 1000)  # timestamps are stored x100 this db
        mid: str = unwrap(row["mid"])
        # TODO perhaps we could be defensive with null sender/chat etc and still emit the Visit
        sender: str = unwrap(row["sender"])
        chatname: str = unwrap(row["chatname"])
        sender: str = unwrap(row["sender"])
        tags: str = unwrap(row["tags"])
        infojson: str = unwrap(row["infojson"])

        if tags and tags.strip():
            tags = "".join(f"#{t}" for t in tags.split())
            text = f"{text}\n\n{tags}"

        url_title = _parse_json_title(infojson)
        if url_title:
            text = f"title: {url_title}\n\n{text}"

        for u in urls:
            # https://www.reddit.com/r/Telegram/comments/6ufwi3/link_to_a_specific_message_in_a_channel_possible/
            # hmm, only seems to work on mobile app, but better than nothing...
            yield Visit(
                url=unquote(u),
                dt=dt,
                context=text,
                locator=Loc.make(
                    title=f"chat({mid}) from {sender}@{chatname}",
                    href=f"sqlite://{database}?immutable=1#!Messages.EventId={mid}",
                ),
            )

    # TODO yield error if chatname or chat or smth else is null?
    for row in db.query(query_str):
        try:
            yield from _handle_row(row)
        except Exception as ex:
            logger.warning(
                "Cannot extract row: %s, due to: %s(%s)",
                row,
                type(ex).__name__,
                ex,
                exc_info=is_debug,
            )
