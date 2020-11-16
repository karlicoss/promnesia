'''
Uses [[https://github.com/karlicoss/HPI][HPI]] for Pocket highlights & bookmarks
'''
from ..common import Visit, Loc, Results


def index() -> Results:
    from . import hpi
    from my.pocket import articles
    # TODO use docstring from my. module? E.g. describing which pocket format is expected

    for a in articles():
        loc = Loc.make(title='pocket', href=a.pocket_link)
        hls = a.highlights
        if len(hls) == 0:
            yield Visit(
                url=a.url,
                dt=a.added,
                context=None,
                locator=loc,
            )
        for hl in hls:
            yield Visit(
                url=a.url,
                dt=hl.created,
                context=hl.text,
                locator=loc,
            )
