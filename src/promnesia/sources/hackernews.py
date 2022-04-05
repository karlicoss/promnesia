'''
Uses [[https://github.com/karlicoss/HPI][HPI]] dogsheep module to import
Hacker News items.
'''

import textwrap

from promnesia.common import Visit, Loc, Results


def index() -> Results:
    from . import hpi
    from my.hackernews import dogsheep

    for item in dogsheep.items():
        if isinstance(item, Exception):
            yield item
            continue
        hn_url = item.permalink
        title = "hackernews"
        if item.title:
            title = item.title
        elif item.text_html:
            title = item.text_html
            title = textwrap.shorten(
                    title, width=79, placeholder="…",
                    break_long_words=True)
        # The locator is always the HN story. If the story is a link (as
        # opposed to a text post), we insert a visit such that the link
        # will point back to the corresponding HN story.
        loc = Loc.make(title=title, href=hn_url)
        urls = [hn_url]
        if item.url is not None:
            urls.append(item.url)
        for url in urls:
            yield Visit(
                    url=url,
                    dt=item.created,
                    locator=loc,
                    context=title,
            )
