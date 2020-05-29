'''
Uses [[https://github.com/karlicoss/HPI][HPI]] for Pocket highlights & bookmarks
'''
from ..common import Visit, Loc, Results


def index() -> Results:
    from my.pocket import get_articles
    # TODO use docstring from my. module? E.g. describing which pocket format is expected

    for a in get_articles():
        # TODO not sure if can make more specific link on pocket?
        loc = Loc.make(title='pocket', href=a.pocket_link)  # type: ignore[attr-defined]
        hls = a.highlights  # type: ignore[attr-defined]
        if len(hls) == 0:
            yield Visit(
                url=a.url, # type: ignore[attr-defined]
                dt=a.added, # type: ignore[attr-defined]
                context=None,
                locator=loc,
            )
        for hl in hls:
            yield Visit(
                url=a.url, # type: ignore[attr-defined]
                dt=hl.created,
                context=hl.text,
                locator=loc,
            )
# TODO to properly typecheck, add pockexport, hypexport etc., cloning to lint script
