'''
Uses HPI [[https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#myreddit][reddit]] module
'''

from itertools import chain
from typing import Set, Optional, Type

from ..common import Visit, Loc, extract_urls, Results, logger


def index(*, render_markdown: bool = False, renderer: Optional[Type['RedditRenderer']] = None) -> Results:
    from . import hpi
    try:
        from my.reddit.all import submissions, comments, saved, upvoted
    except ModuleNotFoundError as e:
        if "No module named 'my.reddit.all'" in str(e):
            import warnings
            warnings.warn("DEPRECATED/reddit: Using an old version of HPI, please update")
            from my.reddit import submissions, comments, saved, upvoted  # type: ignore[no-redef]
        else:
            raise e

    if renderer is not None:
        assert callable(renderer), f"{renderer} is not a callable (should be a subclass of RedditRenderer)"
        r = renderer(render_markdown=render_markdown)
    else:
        r = RedditRenderer(render_markdown=render_markdown)

    logger.info('processing saves')
    for s in saved():
        try:
            yield from r._from_save(s)
        except Exception as e:
            yield e

    logger.info('processing comments')
    for c in comments():
        try:
            yield from r._from_comment(c)
        except Exception as e:
            yield e

    logger.info('processing submissions')
    for sub in submissions():
        try:
            yield from r._from_submission(sub)
        except Exception as e:
            yield e

    logger.info('processing upvotes')
    for u in upvoted():
        try:
            yield from r._from_upvote(u)
        except Exception as e:
            yield e


# mostly here so we can keep track of how the user
# wants to render markdown
class RedditRenderer:
    def __init__(self, render_markdown: bool = False) -> None:
        self._link_extractor = None
        self._parser_cls = None
        try:
            from .markdown import TextParser, extract_from_text
            self._link_extractor = extract_from_text
            self._parser_cls = TextParser
        except ImportError as import_err:
            # TODO: add dummy _link_extractor and _parser_cls classes incase
            # these are called by a subclass?

            # only send error if the user is trying to enable this feature
            if render_markdown:
                logger.exception(import_err)
                logger.critical("Could not import markdown module to render reddit markdown. Try 'python3 -m pip install mistletoe'")
            render_markdown = False  # force to be false, couldn't import
        self.render_markdown = render_markdown


    def _from_comment(self, i: 'Comment') -> Results:
        locator = Loc.make(
            title='Reddit comment',
            href=i.url,
        )
        yield from self._from_common(i, locator=locator)


    def _from_submission(self, i: 'Submission') -> Results:
        locator = Loc.make(
            title=f'Reddit submission: {i.title}',
            href=i.url,
        )
        yield from self._from_common(i, locator=locator)


    def _from_upvote(self, i: 'Upvote') -> Results:
        locator = Loc.make(
            title=f'Reddit upvote',
            href=i.url,
        )
        yield from self._from_common(i, locator=locator)


    def _from_save(self, i: 'Save') -> Results:
        locator = Loc.make(
            title='Reddit save',
            href=i.url,
        )
        yield from self._from_common(i, locator=locator)


    # to allow for possible subclassing by the user?
    def _render_body(self, text: str) -> str:
        if self.render_markdown and self._parser_cls is not None:
            return self._parser_cls(text)._doc_ashtml()
        else:
            return text


    def _from_common(self, i: 'RedditBase', locator: Loc) -> Results:
        urls = [i.url]
        # TODO this should belong to HPI.. fix permalink handling I guess
        # ok, it's not present for all of them..
        lurl = i.raw.get('link_url')
        if lurl is not None:
            urls.append(lurl)
        lurl = i.raw.get('url')
        if lurl is not None:
            urls.append(lurl)

        context = self._render_body(i.text)

        emitted: Set[str] = set()

        for url in chain(urls, extract_urls(i.text)):
            if url in emitted:
                continue
            yield Visit(
                url=url,
                dt=i.created,
                context=context,
                locator=locator,
            )
            emitted.add(url)

        # extract from markdown links like [link text](https://...)
        # incase URLExtract missed any
        #
        # this should try to do this, even if the user didn't enable
        # the render_markdown flag, as it may catch extra links that URLExtract didnt
        # would still require mistletoe to be installed, but
        # the user may already have it installed for the auto/markdown modules
        if self._link_extractor is not None:
            for res in self._link_extractor(i.text):
                if isinstance(res, Exception):
                    yield res
                    continue
                if res.url in emitted:
                    continue
                yield Visit(
                    url=res.url,
                    dt=i.created,
                    context=context,
                    locator=locator,
                )
                emitted.add(res.url)


import typing
if typing.TYPE_CHECKING:
    from my.reddit.common import Submission, Comment, Save, Upvote, RedditBase

