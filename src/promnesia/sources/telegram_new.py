from urllib.parse import unquote # TODO mm, make it easier to rememember to use...

from promnesia.common import Results, logger, extract_urls, Visit, Loc


def index()  -> Results:
    from . import hpi
    from my.telegram.telegram_backup import messages

    # TODO port from old module
    # TODO - http_only
    # TODO - text_query and handling json column
    for i, m in enumerate(messages()):
        text = m.text

        urls = extract_urls(text)
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
