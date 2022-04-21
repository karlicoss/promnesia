'''
Uses HPI [[https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#mygoogletakeoutpaths][google.takeout]] module
'''
from typing import Iterable, Set, Type
import warnings

from ..common import Visit, Loc, Results, logger
from ..compat import removeprefix


def index() -> Results:
    from . import hpi

    try:
        from my.google.takeout.parser import events
        from google_takeout_parser.models import Activity, YoutubeComment, LikedYoutubeVideo, ChromeHistory, PlayStoreAppInstall, Location
    except ModuleNotFoundError as ex:
        logger.exception(ex)
        yield ex

        warnings.warn("Please set up my.google.takeout.parser module for better takeout support. Falling back to legacy implementation.")

        from . import takeout_legacy
        yield from takeout_legacy.index()
        return

    _seen: Set[Type] = {
        # these are definitely not useful for promnesia
        Location,
        PlayStoreAppInstall,
    }
    def warn_once_if_not_seen(e) -> Iterable[Exception]:
        et = type(e)
        if et in _seen:
            return
        _seen.add(et)
        yield RuntimeError(f"Unhandled event {et}: {e}")

    for e in events():
        if isinstance(e, Exception):
            yield e
            continue
        elif isinstance(e, Activity):
            # TODO: regex out title and use it as locator title?
            url = e.titleUrl
            if url is not None:
                # when you follow something from search the actual url goes after this
                # e.g. https://www.google.com/url?q=https://en.wikipedia.org/wiki/Clapham
                # note: also title usually starts with 'Visited ', in such case but perhaps fine to keep it
                url = removeprefix(url, "https://www.google.com/url?q=")

                yield Visit(
                    url=url,
                    dt=e.time,
                    context=e.header,
                    locator=Loc(title=e.title, href=url),
                )
            for s in e.subtitles:
                surl = s[1]
                if surl is not None:
                    if "youtube.com/channel" in surl:
                        continue
                    yield Visit(
                        url=surl,
                        dt=e.time,
                        context=s[0],
                        locator=Loc(title=e.title, href=surl),
                    )
        elif isinstance(e, ChromeHistory):
            yield Visit(
                url=e.url,
                dt=e.dt,
                locator=Loc(title=e.title, href=e.url),
            )
        elif isinstance(e, LikedYoutubeVideo):
            yield Visit(
                url=e.link, dt=e.dt, context=e.desc, locator=Loc(title=e.title, href=e.link)
            )
        elif isinstance(e, YoutubeComment):
            for url in e.urls:
                # todo: use url_metadata to improve locator?
                # or maybe just extract first sentence?
                yield Visit(
                    url=url, dt=e.dt, context=e.content, locator=Loc(title=e.content, href=url)
                )
        else:
            yield from warn_once_if_not_seen(e)
