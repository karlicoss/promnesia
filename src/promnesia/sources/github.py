'''
Uses [[https://github.com/karlicoss/HPI][HPI]] github module
'''

from itertools import chain

from ..common import Results, Visit, Loc, iter_urls


def index() -> Results:
    from . import hpi
    from my.github.all import events

    for e in events():
        if isinstance(e, Exception):
            yield e
            continue
        if e.link is None:
            continue

        # locator should link back to this event
        loc = Loc.make(title=e.summary, href=e.link)

        # visit which include links to this event in particular
        yield Visit(
            url=e.link,
            dt=e.dt,
            context=e.body,
            locator=loc,
        )

        if e.body is None:
            continue

        # TODO: probably includes lots of filenames
        # which get mismatched as urls? check if they're
        # prefixed with http/www/find some way to ignore
        # filenames (ends with .py? .js? .html?)
        #
        # extract any links found in the summary / body
        for url in chain(iter_urls(e.summary), iter_urls(e.body)):
            yield Visit(
                url=url,
                dt=e.dt,
                context=e.body,
                locator=loc,
            )
