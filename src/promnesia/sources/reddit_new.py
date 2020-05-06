from itertools import chain
from typing import Iterable

from ..common import Visit, Loc, extract_urls, Extraction


from my.reddit import Submission, Comment, Save, Upvote
from my.reddit import submissions, comments, saved, upvoted


def index() -> Iterable[Extraction]:
    # TODO should probably use markdown parser here?

    for s in saved():
        try:
            yield from _from_save(s)
        except Exception as e:
            yield e

    for c in comments():
        try:
            yield from _from_comment(c)
        except Exception as e:
            yield e

    for sub in submissions():
        try:
            yield from _from_submission(sub)
        except Exception as e:
            yield e

    for u in upvoted():
        try:
            yield from _from_upvote(u)
        except Exception as e:
            yield e


# TODO not sure if worthy a Protocol?? duplication is a bit annoying..

def _from_save(i: Save) -> Iterable[Extraction]:
    locator = Loc.make(
        title='saved',
        href=i.url,
    )
    # TODO FIXME should probably use markdown link parser throughout the module
    # TODO worth having the link that was submitted?
    # it's different from the reddit link
    for url in chain([i.url], extract_urls(i.text)):
        yield Visit(
            url=url,
            dt=i.created,
            context=i.text,
            locator=locator,
        )


def _from_comment(i: Comment) -> Iterable[Extraction]:
    locator = Loc.make(
        title='comment',
        href=i.url,
    )
    for url in chain([i.url], extract_urls(i.text)):
        yield Visit(
            url=url,
            dt=i.created,
            context=i.text,
            locator=locator,
        )


def _from_submission(i: Submission) -> Iterable[Extraction]:
    locator = Loc.make(
        title=f'submission: {i.title}',
        href=i.url,
    )
    for url in chain([i.url], extract_urls(i.text)):
        yield Visit(
            url=url,
            dt=i.created,
            context=i.text,
            locator=locator,
        )


def _from_upvote(i: Submission) -> Iterable[Extraction]:
    locator = Loc.make(
        title=f'upvoted',
        href=i.url,
    )
    for url in chain([i.url], extract_urls(i.text)):
        yield Visit(
            url=url,
            dt=i.created,
            context=i.text,
            locator=locator,
        )
