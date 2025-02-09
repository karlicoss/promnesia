'''
Uses [[https://github.com/karlicoss/HPI][HPI]] for Pocket highlights & bookmarks
'''

from promnesia.common import Loc, Results, Visit


def index() -> Results:
    from . import hpi  # noqa: F401,I001
    from my.pocket import articles

    # TODO use docstring from my. module? E.g. describing which pocket format is expected

    for a in articles():
        title = a.json.get('resolved_title', None) or a.json.get('given_title', 'pocket')
        loc = Loc.make(title=title, href=a.pocket_link)
        # Add a reverse locator so that the Promnesia browser extension shows a
        # link on the Pocket page back to the original URL.
        # FIXME need to actually use it
        _loc_rev = Loc.make(title=title, href=a.url)
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
