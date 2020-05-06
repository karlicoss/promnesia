from itertools import chain
from typing import Iterable

from ..common import Visit, Loc, extract_urls, Extraction


from my.reddit import Save
from my.reddit import submissions, comments, saved, upvoted


def index() -> Iterable[Extraction]:
    # TODO should probably use markdown parser here?

    for s in saved():
        try:
            yield from _from_save(s)
        except Exception as e:
            yield e
    # TODO FIXME process the rest


def _from_save(s: Save) -> Iterable[Extraction]:
    locator = Loc.make(
        title='Reddit save',
        href=s.url,
    )
    # TODO FIXME should probably use markdown link parser throughout the module
    # TODO worth having the link that was submitted?
    # it's different from the reddit link
    for url in chain([s.url], extract_urls(s.text)):
        yield Visit(
            url=url,
            dt=s.created,
            context=s.text,
            locator=locator,
        )
