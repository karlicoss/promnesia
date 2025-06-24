'''
Uses [[https://github.com/karlicoss/HPI][HPI]] smscalls module
'''

from promnesia.common import Loc, Results, Visit, extract_urls


def index() -> Results:
    from . import hpi  # noqa: F401,I001
    from my.smscalls import messages

    for m in messages():
        if isinstance(m, Exception):
            yield m
            continue

        urls = extract_urls(m.message)
        if len(urls) == 0:
            continue

        if m.who is None:
            loc = Loc(title=f"SMS with {m.phone_number}")
        else:
            loc = Loc(title=f"SMS with {m.who} ({m.phone_number})")

        for u in urls:
            yield Visit(
                url=u,
                dt=m.dt,
                context=m.message,
                locator=loc,
            )
