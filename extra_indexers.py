"""
This file contains stuff that's I'm using but which would be hard to share with other people because of private data sources etc
So this isn't worth moving in the main package but could be useful as a reference.
"""
from promnesia.common import extract_urls, get_logger, PreVisit, Loc

# ok, so it doesn't necessarily have everything in entities...
# {
#   "retweeted" : false,
#   "source" : "<a href=\"http://twitter.com\" rel=\"nofollow\">Twitter Web Client</a>",
#   "entities" : {
#     "hashtags" : [ ],
#     "symbols" : [ ],
#     "user_mentions" : [ ],
#     "urls" : [ ]
#   },
#   "display_text_range" : [ "0", "56" ],
#   "favorite_count" : "0",
#   "id_str" : "9982607217",
#   "truncated" : false,
#   "retweet_count" : "0",
#   "id" : "9982607217",
#   "created_at" : "Thu Mar 04 17:29:08 +0000 2010",
#   "favorited" : false,
#   "full_text" : "http://old.slackware.ru/article.ghtml?ID=544  Забавно =)",
#   "lang" : "ru"
# }
def twitter_indexer():
    import my.tweets
    logger = get_logger()
    for t in my.tweets.tweets_all():
        # TODO hmm. tweets themselves are sort of visits? not sure if should contribute..
        ents = t.tw.entities
        # TODO ents shouldn't really be None.. figure it out in twidump, perhaps None is returned by api?
        urls = [] if ents is None else [eu.expanded_url for eu in ents.urls]
        if len(urls) == 0:
            # if entities haven't detected anything it usually means RT or reply in my case, so worth trying again to extract
            # e.g. replies from json twitter takeouts don't seem to have entities set
            urls = extract_urls(t.text)
            # t.co refer to the retweeted tweet, so perhaps not very meaningful
            urls = [u for u in urls if '/t.co/' not in u]
        loc = Loc.make(title='twitter', href=t.url)
        for u in urls:
            yield PreVisit(
                url=u,
                dt=t.dt,
                context=t.text,
                locator=loc,
            )


def instapaper_indexer():
    import my.new.instapaper as ip
    logger = get_logger()
    for p in ip.get_pages():
        bm = p.bookmark
        hls = p.highlights

        def pv(**kwargs):
            return PreVisit(
                url=bm.url,
                **kwargs,
            )

        if len(hls) == 0:
            yield pv(
                dt=bm.dt,
                context=None,
                locator=Loc.make(title='instapaper', href=bm.instapaper_link),
            )
        else:
            for hl in p.highlights:
                cparts = [hl.text]
                if hl.note is not None:
                    cparts.append('comment: ' + hl.note)
                yield pv(
                    dt=hl.dt,
                    context='\n'.join(cparts),
                    locator=Loc.make(title='instapaper', href=hl.instapaper_link),
                )


