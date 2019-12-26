from pathlib import Path
from typing import Iterator, Optional

from ..common import Extraction, get_logger, Visit, Loc, PathIsh

from my.pocket import get_articles


def index(export_path: Optional[PathIsh]=None) -> Iterator[Extraction]:
    assert export_path is not None
    # TODO FIXME
    # TODO use docstring from my. module? E.g. describing which pocket format is expected
    # ip.configure(export_path=export_path)

    for a in get_articles(Path(export_path)):
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
