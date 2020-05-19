'''
Uses HPI [[https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#myreddit][reddit]] module
'''

from itertools import chain
from typing import Iterable

from ..common import Visit, Loc, extract_urls, Extraction, get_logger


from my.reddit import Submission, Comment, Save, Upvote
from my.reddit import submissions, comments, saved, upvoted


def index() -> Iterable[Extraction]:
    logger = get_logger()
    # TODO should probably use markdown parser here?

    logger.info('processing saves')
    for s in saved():
        try:
            yield from _from_save(s)
        except Exception as e:
            yield e

    logger.info('processing comments')
    for c in comments():
        try:
            yield from _from_comment(c)
        except Exception as e:
            yield e

    logger.info('processing submissions')
    for sub in submissions():
        try:
            yield from _from_submission(sub)
        except Exception as e:
            yield e

    logger.info('processing upvotes')
    for u in upvoted():
        try:
            yield from _from_upvote(u)
        except Exception as e:
            yield e


def _from_save(i: Save) -> Iterable[Extraction]:
    locator = Loc.make(
        title='Reddit save',
        href=i.url,
    )
    yield from _from_common(i, locator=locator)


def _from_comment(i: Comment) -> Iterable[Extraction]:
    locator = Loc.make(
        title='Reddit comment',
        href=i.url,
    )
    yield from _from_common(i, locator=locator)


def _from_submission(i: Submission) -> Iterable[Extraction]:
    locator = Loc.make(
        title=f'Reddit submission: {i.title}',
        href=i.url,
    )
    yield from _from_common(i, locator=locator)


def _from_upvote(i: Upvote) -> Iterable[Extraction]:
    locator = Loc.make(
        title=f'Reddit upvote',
        href=i.url,
    )
    yield from _from_common(i, locator=locator)


def _from_common(i: 'RedditThing', locator: Loc) -> Iterable[Extraction]:
    urls = [i.url]
    # TODO this should belong to HPI.. fix permalink handling I guess
    # ok, it's not present for all of them..
    lurl = i.raw.get('link_url')
    if lurl is not None:
        urls.append(lurl)
    lurl = i.raw.get('url')
    if lurl is not None:
        urls.append(lurl)

    for url in chain(urls, extract_urls(i.text)):
        yield Visit(
            url=url,
            dt=i.created,
            context=i.text,
            locator=locator,
        )


from datetime import datetime
import typing
if typing.TYPE_CHECKING:
    # TODO define in rexport?
    from typing_extensions import Protocol
    from typing import Dict, Any
    class RedditThing(Protocol):
        @property
        def raw(self) -> Dict[str, Any]: ...
        @property
        def url(self) -> str: ...
        @property
        def created(self) -> datetime: ...
        @property
        def text(self) -> str: ...

# TODO should probably use markdown link parser throughout the module
