'''
Indexes [[https://github.com/fabianonline/telegram_backup#readme][telegram_backup]] databases through HPI's [[https://github.com/karlicoss/HPI/blob/master/src/my/telegram/telegram_backup.py][my.telegram.telegram_backup]] provider.
'''

from __future__ import annotations

import warnings
from urllib.parse import unquote  # TODO mm, make it easier to rememember to use...

from promnesia.common import Loc, PathIsh, Results, Visit, extract_urls


def index(database: PathIsh | None = None, *, http_only: bool = False, with_extra_media_info: bool = False) -> Results:
    from . import hpi  # noqa: F401

    if database is None:
        yield from _index_messages(http_only=http_only, with_extra_media_info=with_extra_media_info)
        return

    warnings.warn(
        'Passing a database path to promnesia.sources.telegram is deprecated. '
        'Set my.config.telegram.telegram_backup.export_path to your telegram_backup database.',
        stacklevel=2,
    )
    yield from _index_database(database, http_only=http_only, with_extra_media_info=with_extra_media_info)


def _index_database(database: PathIsh, *, http_only: bool, with_extra_media_info: bool) -> Results:
    from my.core.cfg import tmp_config

    class config:
        class telegram:
            class telegram_backup:
                export_path: PathIsh = database

    with tmp_config(modules='my.telegram.telegram_backup', config=config):
        yield from _index_messages(http_only=http_only, with_extra_media_info=with_extra_media_info)


def _index_messages(*, http_only: bool, with_extra_media_info: bool) -> Results:
    from my.telegram.telegram_backup import messages

    extra_where = "(has_media == 1 OR text LIKE '%http%')" if http_only else None
    for m in messages(
        with_extra_media_info=with_extra_media_info,
        extra_where=extra_where,
    ):
        text = m.text

        urls = extract_urls(text)
        extra_media_info = m.extra_media_info
        if extra_media_info is not None:
            urls.extend(extract_urls(extra_media_info))

        if len(urls) == 0:
            continue

        dt = m.time
        sender = m.sender.name
        chat = m.chat

        cname = chat.name if chat.name is not None else str(chat.id)

        locator = Loc.make(
            title=f"chat with {cname}",
            href=m.permalink,
        )
        context = f'{sender}: {text}'

        for u in urls:
            yield Visit(
                url=unquote(u),
                dt=dt,
                context=context,
                locator=locator,
            )
