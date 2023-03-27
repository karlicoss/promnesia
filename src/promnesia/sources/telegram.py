from typing import Optional
from urllib.parse import unquote # TODO mm, make it easier to rememember to use...
import warnings

from promnesia.common import Results, logger, extract_urls, Visit, Loc, PathIsh


def index(database: Optional[PathIsh]=None, *, http_only: bool=False, with_extra_media_info: bool=False)  -> Results:
    if database is None:
        # fully relying on HPI
        yield from _index_new(http_only=http_only, with_extra_media_info=with_extra_media_info)
        return

    warnings.warn(
        f'Passing paths to promnesia.sources.telegram is deprecated, you should setup my.telegram.telegram_backup instead. '
        f'Will try to hack database path {database} into HPI config.'
    )
    try:
        yield from _index_new_with_adhoc_config(database=database, http_only=http_only, with_extra_media_info=with_extra_media_info)
        return
    except Exception as e:
        logger.exception(e)
        warnings.warn("Hacking my.config.telegram.telegram_backup didn't work. You probably need to update HPI.")

    logger.warning("Falling back onto promnesia.sources.telegram_legacy module")
    yield from _index_legacy(database=database, http_only=http_only)


def _index_legacy(*, database: PathIsh, http_only: bool) -> Results:
    from . import telegram_legacy
    yield from telegram_legacy.index(database=database, http_only=http_only)


def _index_new_with_adhoc_config(*, database: PathIsh, http_only: bool, with_extra_media_info: bool) -> Results:
    from . import hpi

    class config:
        class telegram:
            class telegram_backup:
                export_path: PathIsh = database

    from my.core.cfg import tmp_config
    with tmp_config(modules='my.telegram.telegram_backup', config=config):
        yield from _index_new(http_only=http_only, with_extra_media_info=with_extra_media_info)


def _index_new(*, http_only: bool, with_extra_media_info: bool) -> Results:
    from . import hpi
    from my.telegram.telegram_backup import messages

    extra_where = "(has_media == 1 OR text LIKE '%http%')" if http_only else None
    for i, m in enumerate(messages(
            with_extra_media_info=with_extra_media_info,
            extra_where=extra_where,
    )):
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
