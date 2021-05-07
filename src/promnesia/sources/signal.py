"""
Harvest visits from Signal Desktop's chiphered SQLIite db(s).

Functions get their defaults from module-data.

* Open-ciphered-db adapted from:
  https://github.com/carderne/signal-export/commit/2284c8f4
* Copyright (c) 2019 Chris Arderne, 2020 Kostis Anagnostopoulos
"""

import json
import logging
import platform
import sqlite3
import subprocess as sbp
from contextlib import contextmanager
from pathlib import Path
from textwrap import dedent, indent
from typing import Any, Iterable, Iterator, Mapping, Sequence, Union

from ..common import Loc, PathIsh, Results, Visit, extract_urls, from_epoch

PathIshes = Union[PathIsh, Iterable[PathIsh]]


def index(
    *db_paths: PathIsh,
    http_only: bool = None,
    locator_schema="editor",
    append_platform_path: bool = None,
    override_key: str = None,
) -> Results:
    """
    :param db_paths:
        path(s) to Signal-desktop's db; if none given,
        uses platform's default (see :data:`platform_db_paths`)
        unless `append_platform_path` is false (default)
    :param http_only:
        when true, do not collect IP-addresses and strings like `"python.py"`
        (filtered early, when querying signal-desktop's db)
    :param locator_schema:
        the url-schema to use for the constructing the links for each visit
    :param append_platform_path:
        a tri-state boolean fed to :func:`collect_db_paths(),
        if true, use given `db_paths` in addition to :data:`platform_db_paths`,
        if None, assume true only when no `db_paths` given.
    :param override_key:
        an optional hex string (e.g. "baddeadbeafdad") fed to :func:`_harvest_db()`,
        when not given, extracted from :file:`../config.json` relative to each file in `db_paths`,
        otherwise, this same key is used for harvesting all db-files.
    """
    logger.debug(
        "http_only?(%s), locator_schema?(%s), append_platform_path?(%s), "
        "overide_key given?(%s), db_paths: %s",
        http_only,
        locator_schema,
        append_platform_path,
        "yes" if override_key else "no",
        db_paths,
    )
    resolved_db_paths = collect_db_paths(*db_paths, append=append_platform_path)
    logger.debug("Paths to harvest: %s", db_paths)
    if not http_only:
        messages_query += "\nWHERE body LIKE '%http%'"

    for db_path in resolved_db_paths:
        logger.info("Ciphered db to harvest %s", db_path)
        assert db_path.is_file(), f"Is it a (Signal-desktop sqlite) file? {db_path}"
        yield from _harvest_db(
            db_path,
            messages_query,
            override_key=override_key,
            locator_schema=locator_schema,
        )


logger = logging.getLogger(__name__)

#: A mapping of ``platform.system()`` values --> (possibly globbing) paths.
platform_db_paths: Mapping[str, PathIsh] = {
    "Linux": "~/.config/Signal/sql/db.sqlite",
    "Darwin": "~/Library/Application Support/Signal/sql/db.sqlite",
    "Windows": "~/AppData/Roaming/Signal/sql/db.sqlite",
}
#: SQL PRAGMAs sent before opening the database (after ``PRAGMA key = x'...';``)
decryption_pragmas = {
    ## Not required, but good to be explicit.
    "cipher_compatibility": 4,
    ## Really old installation?
    # "cipher_compatibility": 3,
    ## Pragmas for cipher_compatibility-4:
    # "cipher_page_size": "4096",
    # "cipher_hmac_algorithm": "HMAC_SHA512",
    # "cipher_kdf_algorithm": "PBKDF2_HMAC_SHA512",
    ## Pragmas for cipher_compatibility-3
    # "cipher_page_size": "1024",
    # "cipher_hmac_algorithm": "HMAC_SHA1",
    # "cipher_kdf_algorithm": "PBKDF2_HMAC_SHA1",
}

messages_query = dedent(
    """
    WITH
    Cons AS (
        SELECT
            id,
            type,
            coalesce(name, profileName, profileFamilyName, e164) as aname,
            name,
            profileName,
            profileFamilyName,
            e164,
            uuid
        FROM conversations
    ),
    Msgs AS (
        SELECT
            M.id,
            M.type as mtype,
            M.isErased,
            coalesce(
                M.received_at,
                M.sent_at
            ) AS timestamp,
            IIF(M.type = "outgoing",
                "Me (" || C2.aname || ")",
                C2.aname
            ) AS sender,
            M.conversationId AS cid,
            C1.aname AS chatname,
            C1.name,
            C1.profileName,
            C1.profileFamilyName,
            C1.type as ctype,
            M.body
        FROM messages as M
        INNER JOIN Cons AS C1
            ON M.conversationId = C1.id
        INNER JOIN Cons AS C2
            ON M.sourceUuid = C2.uuid
    )
    SELECT id, timestamp, sender, cid, chatname, body
    FROM Msgs
    """
)


def _is_pathish(p) -> bool:
    """returns true if str or pathlin.Path."""
    return isinstance(p, (str, Path))


def _expand_path(path_pattern: PathIsh = None) -> Iterable[Path]:
    """
    Expand homedir(`~`) and globs any file-paths matched.

    :param path_pattern:
        a path ike ``~/foo/**/bar*ish``; CWD assumed if missing/empty/None

    :returns:
        resolved ``Path`` instances

    Expansion code adapted from https://stackoverflow.com/a/51108375/548792
    to handle also degenerate cases (``'', '.', '/'``):

    >>> str(next(iter(_get_files('/'))))
    '/'

    >>> import os; cwd = os.getcwd()
    >>> [
    ...     str(i) == cwd
    ...     for i in (
    ...         *_get_files(''),
    ...         *_get_files('.'),
    ...     )
    ... ]
    [True, True]
    """
    path = Path(path_pattern or "").expanduser()
    # Since ``path.glob(pattern)`` supports only relative patterns.
    # extract it from given input.
    # But note that '/'  and '.' or '' bring empty parts.
    parts = path.parts[path.is_absolute() :]
    path = Path(path.root).resolve()
    return path.glob(str(Path(*parts))) if parts else [path]


def _expand_paths(paths: PathIshes) -> Iterable[Path]:
    if _is_pathish(paths):
        paths = [paths]  # type: ignore[assignment,list-item]
    return [pp.resolve() for p in paths for pp in _expand_path(p)]  # type: ignore[union-attr,list-item]


def collect_db_paths(*db_paths: PathIsh, append: bool = None) -> Iterable[Path]:
    """
    Get OS-dependent (or user overridden) db locations (1st existing used).

    :param db_paths:
        optional path(s) to search for db file in-order, overriding OS-platform's defaults.
    :param append:
        a tri-state boolean,
        if true, use given `db_paths` in addition to :data:`platform_db_paths`
        if None, assume true only when no paths given.
    :returns:
        one or more pathish

    Note: needed `append` here, to resolve paths.

    >>> bool(collect_db_paths())  # my home-path
    True
    >>> collect_db_paths(None)
    []
    >>> collect_db_paths([])
    []
    >>> collect_db_paths('NOT_EXISTS')
    []
    >>> collect_db_paths("~/..")  # posix-only
    [PosixPath('/home')]
    >>> collect_db_paths('NOT_EXISTS', '/usr/*')
    [PosixPath('/usr/lib'),
     PosixPath('/usr/local'),
     PosixPath('/usr/share'),
    ...
    >>> len(collect_db_paths('/usr', append=True)) - len(collect_db_paths('/usr'))
    1
    """
    if append or not db_paths:
        platform_name = platform.system()
        try:
            plat_paths = platform_db_paths[platform_name]
        except LookupError:
            raise ValueError(
                f"Unknown platform({platform_name}!"
                f"\n  Expected one of {list(platform_db_paths.keys())}."
            )

        if db_paths and append:
            db_paths = [  # type: ignore[misc,assignment]
                *([db_paths] if _is_pathish(db_paths) else db_paths),
                plat_paths,
            ]
        else:
            db_paths = plat_paths  # type: ignore[assignment]

    return _expand_paths(db_paths)


def _config_for_dbfile(db_path: Path, default_key=None) -> Path:
    """Return `default_key` if :file:`{db_path}/../config.json`` does not exist."""
    cfg_path = db_path.parents[1] / "config.json"
    return cfg_path


def _key_from_config(signal_desktop_config_path: PathIsh) -> str:
    with open(signal_desktop_config_path, "r") as conf:
        return json.load(conf)["key"]


@contextmanager
def connect_db(
    db_path: Path,
    key,
    decrypt_db: bool = None,
    sqlcipher_exe: PathIsh = "sqlcipher",
    **decryption_pragmas: Mapping[str, Any],
) -> Iterator[sqlite3.Connection]:
    """
    Opens (or decrypt) a ciphered sqlite db in a context.

    :param key:
        a hex string as extracted from :file:`config.json' (e.g. "baddeadbeafdad")
        see https://www.zetetic.net/sqlcipher/sqlcipher-api/#PRAGMA_key
    :param decrypt_db:
        if true, fully decrypt db into a temporary db-file using `sqlcipher` standalone program;
        the program must be in the PATH, or its path given in `sqlcipher_exe`.
        The temporary db-file is deleted when the context is exited.

        NOTE: The ``pysqlcipher3`` python library is not imported.
    :param sqlcipher_exe:
        the path to the `sqlcipher` standalone program;  only used if `decrypt_db` is true.
    :param decryption_pragmas:
        used to unlock older dbs;  see :data:`decryption_pragmas`.

    :returns:
        the db-connection, which is closed when the context is exited
    :raises pysqlcipher3.dbapi2.DatabaseError:
        when key was invalid and `decrypt_db` was false
    :raises sbp.SubprocessError:
        when key is invalid and `decrypt_db` was true,
        with text _"file is not a database"_
    """
    logger.info(
        "Opening encrypted-db%s: %s",
        db_path,
        f" with {sqlcipher_exe}" if decrypt_db else "",
    )
    db: sqlite3.Connection = None  # type: ignore[assignment]
    decrypted_file = None
    sql_cmds = [
        f"PRAGMA key = \"x'{key}'\";",
        *(f"PRAGMA {k} = {v};" for k, v in decryption_pragmas.items()),
    ]

    try:
        if decrypt_db:
            decrypted_file = db_path.parent / "db-decrypted.sqlite"
            if decrypted_file.exists():
                decrypted_file.unlink()
            sql_cmds.extend(
                [
                    f"ATTACH DATABASE '{decrypted_file}' AS plaintext KEY '';",
                    f"SELECT sqlcipher_export('plaintext');",
                    f"DETACH DATABASE plaintext;",
                ]
            )
            sql = "\n".join(sql_cmds)
            cmd = [sqlcipher_exe, str(db_path)]
            logger.debug(
                "Decrypting db '%s' with cmd: %s <<<EOF\n%s\nEOF", db_path, cmd, sql
            )
            try:
                sbp.run(  # type: ignore[call-overload]
                    cmd,
                    check=True,
                    input=sql,
                    capture_output=True,
                    universal_newlines=True,
                )
            except sbp.CalledProcessError as ex:
                prefix = " " * 4
                raise sbp.SubprocessError(
                    f"{sqlcipher_exe}: failed with code({ex.returncode}) to decrypt db: {db_path}"
                    f"\n   +--SQL:\n{indent(sql, prefix)}\n  +--STDERR:\n{indent(ex.stderr, prefix)}",
                ) from None
            db = sqlite3.connect(f"file:{decrypted_file}?mode=ro", uri=True)
        else:
            from pysqlcipher3 import dbapi2  # type: ignore[import]

            db = dbapi2.connect(f"file:{db_path}?mode=ro", uri=True)
            # Param-binding doesn't work for pragmas, so use a direct string concat.
            sql = "\n".join(sql_cmds)
            db.executescript(sql)

            ## Check db indeed unlocked.
            #  Check is necessary only here;  The `sqlcipher` method, above, fails early.
            list(db.execute("SELECT count(*) FROM sqlite_master;"))

        yield db
    finally:
        try:
            if db:
                db.close()
        finally:
            if decrypted_file and decrypted_file.exists():
                try:

                    logger.debug("Deleting temporary decrypted db: %s", decrypted_file)
                    decrypted_file.unlink()
                except Exception as ex:
                    logger.warning(
                        "Ignored error while deleting temporary decrypted db file(%s): %s",
                        decrypted_file,
                        ex,
                        exc_info=logger.isEnabledFor(logging.DEBUG),
                    )


def _handle_row(row: tuple, db_path: PathIsh, locator_schema: str) -> Results:
    mid, tstamp, sender, cid, chatname, text = row
    urls = extract_urls(text)
    if not urls:
        return

    assert (
        text and mid and sender and chatname
    ), f"should have eliminated messages without 'http' or missing ids: {row}"

    for u in urls:
        yield Visit(
            url=u,  # URLs in SQLite are not quoted
            dt=tstamp,
            context=text,
            locator=Loc.make(
                title=f"chat({mid}) from {sender}@{chatname}",
                href=f"{locator_schema}://{db_path}#!Messages.EventId={mid}",
            ),
        )


def _harvest_db(
    db_path: Path,
    messages_query: str,
    *,
    override_key: str = None,
    locator_schema: str = "editor",
    decrypt_db: bool = None,
    **decryption_pragmas,
) -> Results:
    """
    Harvest db  `db_path` and yield visits.

    See :func:`connect_db()` for `db_path`, `key` params.

    :param override_key:
        when not given, extracted from :file:`../config.json`` relative to `db_path`
    :param messages_query:
        read code for which columns it must fetch, uses :data:`messages_query` if not given
    :param locator_schema:
        see :func:`index()`
    """
    is_debug = logger.isEnabledFor(logging.DEBUG)

    if override_key:
        key = override_key
    else:
        cfg_path = _config_for_dbfile(db_path)
        key = _key_from_config(cfg_path)

    with connect_db(db_path, key, decrypt_db=decrypt_db, **decryption_pragmas) as db:
        for mid, tstamp, sender, cid, chatname, text in db.execute(messages_query):
            try:
                tstamp = from_epoch(tstamp / 1000.0)
                row = (mid, tstamp, sender, cid, chatname, text)
                yield from _handle_row(row, db_path, locator_schema)
            except Exception as ex:
                # TODO: also insert errors in db
                logger.warning(
                    "Cannot extract row: %s, due to: %s(%s)",
                    row,
                    type(ex).__name__,
                    ex,
                    exc_info=is_debug,
                )
