'''
Uses HPI [[https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#mygoogletakeoutpaths][google.takeout]] module
'''
from typing import Iterable, Set, Any, NamedTuple
import warnings

from ..common import Visit, Loc, Results, logger
from ..compat import removeprefix


# incase user is using an old version of google_takeout_parser
class YoutubeCSVStub(NamedTuple):
    contentJSON: str


def index() -> Results:
    from . import hpi
    import json

    try:
        from my.google.takeout.parser import events
        from google_takeout_parser.models import Activity, YoutubeComment, LikedYoutubeVideo, ChromeHistory
        from google_takeout_parser.parse_csv import reconstruct_comment_content, extract_comment_links
    except ModuleNotFoundError as ex:
        logger.exception(ex)
        yield ex

        warnings.warn("Please set up my.google.takeout.parser module for better takeout support. Falling back to legacy implementation.")

        from . import takeout_legacy
        yield from takeout_legacy.index()
        return


    _seen: Set[str] = {
        # these are definitely not useful for promnesia
        'Location',
        'PlaceVisit',
        'PlayStoreAppInstall',
    }

    imported_yt_csv_models = False
    try:
        from google_takeout_parser.models import CSVYoutubeComment, CSVYoutubeLiveChat
        imported_yt_csv_models = True
    except ImportError:
        # warn user to upgrade google_takeout_parser
        warnings.warn("Please upgrade google_takeout_parser (`pip install -U google_takeout_parser`) to support the new format for youtube comments")
        CSVYoutubeComment = YoutubeCSVStub  # type: ignore[misc,assignment]
        CSVYoutubeLiveChat = YoutubeCSVStub  # type: ignore[misc,assignment]

    def warn_once_if_not_seen(e: Any) -> Iterable[Exception]:
        et_name = type(e).__name__
        if et_name in _seen:
            return
        _seen.add(et_name)
        yield RuntimeError(f"Unhandled event {repr(type(e))}: {e}")

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
                title = e.title

                if e.header == 'Chrome':
                    # title contains 'Visited <page title>' in this case
                    context = None
                    title = removeprefix(title, 'Visited ')
                elif e.header in _CLEAR_CONTEXT_FOR_HEADERS:
                    # todo perhaps could add to some sort of metadata?
                    # only useful for debugging really
                    context = None
                elif e.header in url:
                    # stuff like News only has domain name in the header -- completely useless for promnesia
                    context = None
                elif e.title == f'Used {e.header}':
                    # app usage tracking -- using app name as context is useless here
                    context = None
                elif e.products == ['Android']:
                    # seems to be coming from in-app browser, header contains app name in this case
                    context = None
                elif e.products == ['Ads']:
                    # header contains some weird internal ad id in this case
                    context = None
                else:
                    context = None
                # NOTE: at this point seems that context always ends up as None (at least for @karlicoss as of 20230131)
                # so alternatively could just force it to be None instead of manual dispatching :shrug:
                yield Visit(
                    url=url,
                    dt=e.time,
                    context=context,
                    locator=Loc(title=title, href=url),
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
            # TODO not sure if desc makes sense here since it's not user produced data
            # it's just a part of video meta?
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
        elif imported_yt_csv_models and isinstance(e, CSVYoutubeComment):
            contentJSON = json.loads(e.contentJSON)
            content = reconstruct_comment_content(contentJSON, format='text')
            if isinstance(content, Exception):
                yield content
                continue
            links = extract_comment_links(contentJSON)
            if isinstance(links, Exception):
                yield links
                continue
            context = f"Commented on {e.video_url}"
            for url in links:
                yield Visit(
                    url=url, dt=e.dt, context=content, locator=Loc(title=context, href=url)
                )
            yield Visit(
                url=e.video_url, dt=e.dt, context=content, locator=Loc(title=context, href=e.video_url)
            )
        elif imported_yt_csv_models and isinstance(e, CSVYoutubeLiveChat):
            contentJSON = json.loads(e.contentJSON)
            content = reconstruct_comment_content(contentJSON, format='text')
            if isinstance(content, Exception):
                yield content
                continue
            links = extract_comment_links(contentJSON)
            if isinstance(links, Exception):
                yield links
                continue
            context = f"Commented on livestream {e.video_url}"
            for url in links:
                yield Visit(
                    url=url, dt=e.dt, context=content, locator=Loc(title=context, href=url)
                )
            yield Visit(
                url=e.video_url, dt=e.dt, context=content, locator=Loc(title=context, href=e.video_url)
            )
        else:
            yield from warn_once_if_not_seen(e)


_CLEAR_CONTEXT_FOR_HEADERS = {
    'Google Cloud',
    'Travel',
    'Google Arts & Culture',
    'Drive',
    'Calendar',
    'Google Store',
    'Shopping',
    'News',
    'Help',
    'Books',
    'Google My Business',
    'Google Play Movies & TV',
    'Developers',
    'YouTube',
    'Gmail',
    'Video Search',
    'Google Apps',
    'Google Translate',
    'Ads',
    'Image Search',
    'Assistant',
    'Google Play Store',
    'Android',
    'Maps',
    'Search',
    'Google App',
    'in_app_display_context_client',
    'Play Music',
    'Maps - Navigate & Explore',
    'Google Maps',
    'google.com',
    'Google Play Books',
    'Maps - Navigation & Transit',
}
