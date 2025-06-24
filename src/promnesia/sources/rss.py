'''
Uses [[https://github.com/karlicoss/HPI][HPI]] for RSS data.
'''

from datetime import datetime, timezone

from promnesia.common import Loc, Results, Visit

# arbitrary,  2011-11-04 00:05:23.283+00:00
default_datetime = datetime.fromtimestamp(1320365123, tz=timezone.utc)
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
            context='RSS subscription', # TODO use 'provider', etc?
            locator=locator,
        )
