from typing import Iterator, Optional

from ..common import Extraction, get_logger, Visit, Loc, PathIsh, extract_urls

# TODO run mypy during linting?
# pylint: disable=import-error
import my.tweets as tw # type: ignore


def index(export_path: Optional[PathIsh]=None) -> Iterator[Extraction]:
    tw.configure(export_path=export_path)

    logger = get_logger()
    # TODO hmm. tweets themselves are sort of visits? not sure if they should contribute..
    for t in tw.tweets_all():
        try:
            ets = t.entities
            # TODO entities shouldn't really be None.. figure it out in twidump, perhaps None is returned by api?
            assert ets is not None
            urls = [e['expanded_url'] for e in ets['urls']]
        except Exception as e:
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
                dt=t.dt,
                context=t.text,
                locator=loc,
            )


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
