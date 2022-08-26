'''
Uses [[https://github.com/karlicoss/HPI][HPI]] for Pocket highlights & bookmarks
'''
from ..common import Visit, Loc, Results


def index() -> Results:
    from . import hpi
    from my.pocket import articles

    # TODO use docstring from my. module? E.g. describing which pocket format is expected

    for a in articles():
        title = a.json.get('resolved_title', None) or a.json.get('given_title', 'pocket')
        loc = Loc.make(title=title, href=a.pocket_link)
        # Add a reverse locator so that the Promnesia browser extension shows a
        # link on the Pocket page back to the original URL.
        loc_rev = Loc.make(title=title, href=a.url)
        hls = a.highlights
        excerpt = a.json.get('excerpt', None)
        if len(hls) == 0:
            yield Visit(
                url=a.url,
                dt=a.added,
                context=excerpt,
                locator=loc,
            )
        for hl in hls:
            yield Visit(
                url=a.url,
                dt=hl.created,
                context=hl.text,
                locator=loc,
            )
