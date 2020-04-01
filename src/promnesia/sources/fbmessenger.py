from pathlib import Path
from typing import Iterator, Optional

from ..common import Extraction, get_logger, Visit, Loc, PathIsh, extract_urls

from my.fbmessenger import messages


# TODO rename Extraction to smth shorter? even Result is good enough?
def index() -> Iterator[Extraction]:
    # TODO add db path?
    for m in messages():
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

