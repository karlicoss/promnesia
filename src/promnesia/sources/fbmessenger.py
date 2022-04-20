'''
Uses [[https://github.com/karlicoss/HPI][HPI]] for the messages data.
'''

from ..common import Results, Visit, Loc, extract_urls


def index() -> Results:
    from . import hpi
    from my.fbmessenger import messages
    for m in messages():
        if isinstance(m, Exception):
            yield m
            continue
        text = m.text
        if text is None:
            continue
        urls = extract_urls(text)
        if len(urls) == 0:
            continue

        # TODO m.author would be niceneeds to be implemented in fbmessenger model
        loc = Loc.make(
            title=f'chat with {m.thread.name}',
            # eh, not all threads have nicknames, and not sure how to extract reliably
            href=f'https://www.messenger.com/t/{m.thread.thread_id}',
        )
        for u in urls:
            yield Visit(
                url=u,
                dt=m.dt,
                context=m.text,
                locator=loc,
            )

