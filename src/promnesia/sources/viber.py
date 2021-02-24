"""
Adapted from `telegram.py` to read from `~/.ViberPC/XYZ123/viber.db`
"""

import json
import logging
from os import PathLike
import textwrap
from pathlib import Path
from typing import Optional, TypeVar, Union

from ..common import (
    Loc,
    PathIsh,
    Results,
    Visit,
    extract_urls,
    from_epoch,
)

# TODO potentially, belongs to my. package

# TODO kython?
T = TypeVar("T")

logger = logging.getLogger(__name__)


# TODO move to common?
def _dataset_readonly(db: Path):
    # see https://github.com/pudo/dataset/issues/136#issuecomment-128693122
    import sqlite3

    import dataset  # type: ignore

    creator = lambda: sqlite3.connect(f"file:{db}?immutable=1", uri=True)
    return dataset.connect("sqlite:///", engine_kwargs={"creator": creator})


def messages_query() -> str:
    """
    An SQL-query returning 1 row for each message

    A non-private method, to facilitate experimentation.
    """
    return textwrap.dedent(
        f"""
        /*
        Establish group-names by concatenating:
        - groups explicitely named,
        - multi-groups having a group-leader (PGRole=2), with
        - all the rest groups that (must) have just 2 members,
          me(ContactId=1) & "other+" contacts, so use "other"" as group-name.
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


def _ensure_sqlite_hardlink(db_path: Path) -> Path:
    """
    Hard-link user's db to an ``.sqlite`` path, so locator `file://` urls work

    ... at least in Gnome, where mime-type assumed from the suffix.

    :returns:
        the hard-link's path, or the original `db_path` if not a ``.db`` file.
    :raises:
        any non ``FileExistsError`` exception while hard-linking.
    """
    if db_path.suffix.lower() == ".db":
        new_suffix = ".sqlite"
        sqlite_path = db_path.with_suffix(new_suffix)
        try:
            db_path.link_to(sqlite_path)
        except FileExistsError:
            logger.debug("Ok, link already existed: %s --> %s", db_path, new_suffix)
        return sqlite_path
    return db_path


def _parse_json_title(js) -> str:
    if js and js.strip():
        js = json.loads(js)
        if isinstance(js, dict):
            return js.get("Title")


def _handle_row(row: dict, sqlite_path: PathLike) -> Results:
    text = row["text"]
    urls = extract_urls(text)
    if not urls:
        return

    dt = from_epoch(row["time"] // 1000)  # timestamps are stored x100 this db
    mid: str = row["mid"]
    # TODO perhaps we could be defensive with null sender/chat etc and still emit the Visit
    sender: str = row["sender"]
    chatname: str = row["chatname"]
    sender: str = row["sender"]
    tags: str = row["tags"]
    infojson: str = row["infojson"]

    assert (
        text and mid and sender and chatname
    ), f"sql-query should eliminate messages without 'http' or missing ids: {row}"

    if tags and tags.strip():
        tags = "".join(f"#{t}" for t in tags.split())
        text = f"{text}\n\n{tags}"

    url_title = _parse_json_title(infojson)
    if url_title:
        text = f"title: {url_title}\n\n{text}"

    for u in urls:
        yield Visit(
            url=u,  # URLs in Viber's SQLite are not quoted
            dt=dt,
            context=text,
            locator=Loc.make(
                title=f"chat({mid}) from {sender}@{chatname}",
                href=f"file://{sqlite_path}#!Messages.EventId={mid}",
            ),
        )


def index(database: PathIsh) -> Results:
    is_debug = logger.isEnabledFor(logging.DEBUG)

    # Note: for displaying maybe better not to expand/absolute,
    # but it's safer for debugging resolved.
    database = Path(database).expanduser().resolve().absolute()
    assert database.is_file(), database

    sqlite_path: Path = _ensure_sqlite_hardlink(database)
    query_str = messages_query()

    with _dataset_readonly(database) as db:
        for row in db.query(query_str):
            try:
                yield from _handle_row(row, sqlite_path)
            except Exception as ex:
                # TODO: also insert errors in db
                logger.warning(
                    "Cannot extract row: %s, due to: %s(%s)",
                    row,
                    type(ex).__name__,
                    ex,
                    exc_info=is_debug,
                )
