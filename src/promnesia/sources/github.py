'''
Uses [[https://github.com/karlicoss/HPI][HPI]] github module
'''

# Note: requires the 'mistletoe' module if you enable render_markdown

from typing import Optional, Set

from ..common import Results, Visit, Loc, iter_urls, logger


def index(*, render_markdown: bool = False) -> Results:
    from . import hpi
    from my.github.all import events

    if render_markdown:
        try:
            from .markdown import TextParser, extract_from_text
        except ImportError as import_err:
            logger.exception(import_err)
            logger.critical("Could not import markdown module to render github body markdown. Try 'python3 -m pip install mistletoe'")
            render_markdown = False

    for e in events():
        if isinstance(e, Exception):
            yield e
            continue
        if e.link is None:
            continue

        # if enabled, convert the (markdown) body to HTML
        context: Optional[str] = e.body
        if e.body is not None and render_markdown:
            context = TextParser(e.body)._doc_ashtml()

        # locator should link back to this event
        loc = Loc.make(title=e.summary, href=e.link)

        # visit which links back to this event in particular
        yield Visit(
            url=e.link,
            dt=e.dt,
            context=context,
            locator=loc,
        )

        for url in iter_urls(e.summary):
            yield Visit(
                url=url,
                dt=e.dt,
                context=context,
                locator=loc,
            )

        if e.body is None:
            continue

        # extract any links found in the body
        #
        # Note: this set gets reset every event, is here to
        # prevent duplicates between URLExtract and the markdown parser
        emitted: Set[str] = set()
        for url in iter_urls(e.body):
            if url in emitted:
                continue
            yield Visit(
                url=url,
                dt=e.dt,
                context=context,
                locator=loc,
            )
            emitted.add(url)

        # extract from markdown links like [link text](https://...)
        # incase URLExtract missed any somehow
        if render_markdown:
            for res in extract_from_text(e.body):
                if isinstance(res, Exception):
                    yield res
                    continue
                if res.url in emitted:
                    continue
                yield Visit(
                    url=res.url,
                    dt=e.dt,
                    context=context,
                    locator=loc,
                )
                emitted.add(res.url)
