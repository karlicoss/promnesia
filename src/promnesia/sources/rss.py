from itertools import chain

from ..common import Visit, Loc, extract_urls, Results, get_logger

from datetime import datetime

import pytz

# arbitrary,  2011-11-04 00:05:23.283+00:00
default_datetime = datetime.fromtimestamp(1320365123, tz=pytz.utc)
# TODO FIXME allow for visit not to have datetime?
# I.e. even having context is pretty good!

def index() -> Results:
    from my.rss.all import subscriptions
    for feed in subscriptions():
        # TODO locator should be optional too? although could use direct link in the rss reader interface
        locator = Loc.make(title='my.rss')
        yield Visit(
            url=feed.url,
            dt=feed.created_at or default_datetime,
            context=f'RSS subscription', # TODO use 'provider', etc?
            locator=locator,
        )
