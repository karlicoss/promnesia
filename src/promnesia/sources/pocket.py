from typing import Iterator, Optional

from ..common import Extraction, get_logger, Visit, Loc

from my.pocket import get_articles


def index() -> Iterator[Extraction]:
    # TODO use docstring from my. module? E.g. describing which pocket format is expected

    for a in get_articles():
        # TODO not sure if can make more specific link on pocket?
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
