'''
Uses HPI [[https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#myreddit][reddit]] module
'''

from itertools import chain

from ..common import Visit, Loc, extract_urls, Results, logger


def index() -> Results:
    from . import hpi
    from my.reddit import submissions, comments, saved, upvoted
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


# support lazy imports..
# todo hmm, could do similar stuff in HPI?
import typing
if typing.TYPE_CHECKING:
    from my.reddit import Submission, Comment, Save, Upvote


def _from_save(i: 'Save') -> Results:
    locator = Loc.make(
        title='Reddit save',
        href=i.url,
    )
    yield from _from_common(i, locator=locator)


def _from_comment(i: 'Comment') -> Results:
    locator = Loc.make(
        title='Reddit comment',
        href=i.url,
    )
    yield from _from_common(i, locator=locator)


def _from_submission(i: 'Submission') -> Results:
    locator = Loc.make(
        title=f'Reddit submission: {i.title}',
        href=i.url,
    )
    yield from _from_common(i, locator=locator)


def _from_upvote(i: 'Upvote') -> Results:
    locator = Loc.make(
        title=f'Reddit upvote',
        href=i.url,
    )
    yield from _from_common(i, locator=locator)


def _from_common(i: 'RedditThing', locator: Loc) -> Results:
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
