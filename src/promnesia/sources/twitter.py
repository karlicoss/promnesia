'''
Uses [[https://github.com/karlicoss/HPI][HPI]] for Twitter data.
'''
from typing import Iterable

from ..common import logger, Results, Visit, Loc, extract_urls, Res


def index() -> Results:
    from . import hpi
    import my.twitter.all as tw
    # TODO hmm. tweets themselves are sort of visits? not sure if they should contribute..
    processed = 0

    from my.twitter.archive import Tweet # todo extract to common or something?
    tweets: Iterable[Res[Tweet]] = tw.tweets()
    for t in tweets:
        if isinstance(t, Exception):
            yield t
            continue

        processed += 1
        try:
            urls = t.urls
        except Exception as e: # just in case..
            yield e
            urls = []

        if len(urls) == 0:
            # if entities haven't detected anything it usually means RT or reply in my case, so worth trying again to extract
            # e.g. replies from json twitter takeouts don't seem to have entities set
            urls = extract_urls(t.text)
            # t.co refers to the retweeted tweet, so perhaps not very meaningful
            urls = [u for u in urls if '/t.co/' not in u]

        loc = Loc.make(title='twitter', href=t.permalink)
        for u in urls:
            yield Visit(
                url=u,
                dt=t.created_at,
                context=t.text,
                locator=loc,
            )
    logger.info('processed %d tweets', processed)


# ok, so it doesn't necessarily have everything in entities, eg.
# {
#   "retweeted" : false,
#   "source" : "<a href=\"http://twitter.com\" rel=\"nofollow\">Twitter Web Client</a>",
#   "entities" : {
#     "hashtags" : [ ],
#     "symbols" : [ ],
#     "user_mentions" : [ ],
#     "urls" : [ ]
#   },
#   "full_text" : "http://old.slackware.ru/article.ghtml?ID=544  Забавно =)",
#  ...
# }
