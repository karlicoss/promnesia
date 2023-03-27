from typing import Dict, Any
from urllib.parse import unquote # TODO mm, make it easier to rememember to use...

from promnesia.common import Results, logger, extract_urls, Visit, Loc


def index(*, http_only: bool=False, with_extra_media_info: bool=False)  -> Results:
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
