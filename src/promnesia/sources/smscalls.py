'''
Uses [[https://github.com/karlicoss/HPI][HPI]] smscalls module
'''

from promnesia.common import Visit, Loc, Results, extract_urls


def index() -> Results:
    from . import hpi
    from my.smscalls import messages

    for m in messages():

        urls = extract_urls(m.message)
        if len(urls) == 0:
            continue

        loc = Loc(title=f"SMS with {m.who} ({m.phone_number})")

        for u in urls:
            yield Visit(
                url=u,
                dt=m.dt,
                context=m.message,
                locator=loc,
            )
