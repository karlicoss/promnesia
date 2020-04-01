import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

import pytz

import pyjq # type: ignore

from ..common import (PathIsh, Extraction, Loc, PathIsh, PreVisit, extract_urls, get_logger)
from ..kython import kompress
from ..kython.kjson import JDict, JPath, JsonProcessor


Query = str

# TODO move to kjq?
def jq_drop_keys(keys: List[str]) -> Query:
    return """
def walk(f):
  . as $in
  | if type == "object" then
      reduce keys_unsorted[] as $key
        ( {}; . + { ($key):  ($in[$key] | walk(f)) } ) | f
  elif type == "array" then map( walk(f) ) | f
  else f
  end;
""" + f"""
walk(if type == "object" then with_entries(select(.key | test("{'|'.join(keys)}") | not)) else . end)
"""
# TODO figure out how to check array membership instead of abusing regex



def reddit_indexer(p: PathIsh) -> Iterable[Extraction]:
    logger = get_logger()
    p = Path(p)
    with kompress.open(p, 'r') as fo:
        jj = json.load(fo)
    # TODO eh, this is kinda experimental, not sure if should rely on jq for that or handle everything in JsonProcessor
    jq_filter = jq_drop_keys([
            'resized_icons',
            'icon_url',
            'thumbnail',
            'header_img',
            'icon_img',
            'banner_img',
            'community_icon',
            'banner_background_image',
    ])
    logger.info('extracting via jq: %s', jq_filter)
    try:
        jj = pyjq.one(jq_filter, jj)
    except Exception as ee:
        logger.error('exception while querying. Reproduce via xzcat "%s" | jq "%s"', p, jq_filter)
        raise ee
    urls = collect_reddit(jj)
    for url, ctx, loc, dt in urls:
        yield PreVisit(
            url=url,
            dt=dt,
            locator=loc,
            context=ctx,
            # TODO jq path in debug?? 
        )


def path_matches(kpath, pats):
    if len(kpath) < len(pats):
        return False
    for key, p in zip(kpath, pats):
        if isinstance(p, type):
            if type(key) != p:
                return False
        elif key != p:
            return False
    return True

# TODO eh, I had something for that

def dcoalesce(d, *keys: str):
    for k in keys:
        if k in d:
            return d[k]
    raise ValueError(f'None of {keys} are present')

def reddit_link(rest: str) -> str:
    return f'https://reddit.com{rest}'

class Proc(JsonProcessor):
    def __init__(self) -> None:
        self.logger = get_logger()
        self.items = [] # type: ignore

    def handle_dict(self, value: JDict, path: JPath):
        kp = self.kpath(path)
        # TODO hmm. in case of image submissions both url and making a reddit permalink from 'permalink' field makes sense
        # TODO shit some stuff can be reused in timeline...

        # ok, that's a bit confusing...
        # I suppose displaying all comments on post page is is somewhat justtified?
            # ('permalink',
            #  '/r/orgmode/comments/aagmfh/export_to_html_with_useful_nonrandom_ids_and/engzjh7/'),
            # ('num_reports', None),
            # ('link_permalink',
            #  'https://www.reddit.com/r/orgmode/comments/aagmfh/export_to_html_with_useful_nonrandom_ids_and/'),
            # ('link_url',
            #  'https://github.com/alphapapa/unpackaged.el#export-to-html-with-useful-anchors'),
        # TODO I guess it would be a bit easier when it goes hierarchical? then the latter link would trigger all of the comments as well?
        # e.g.as 'connected' urls in hierarchy..

        # so, for comments:
        # link_url makes not much sense as it's related to the post's url
        # link_permalink as well, although would be good to take it into accoutn. maybe just do it for now

        # permalink is the actual comment, should use it. perhaps use comment body as context?

        for mp, extra in [
                (('saved'      , int), 'saved '),
                (('upvoted'    , int), 'upvoted '),
                (('downvoted'  , int), 'downvoted '),
                (('comments'   , int), 'comment to '),
                (('submissions', int), 'submission '),
        ]:
            if not path_matches(kp, mp):
                continue
            title = dcoalesce(value, 'link_title', 'title')
            pl_suffix = value['permalink']
            permalink = reddit_link(pl_suffix)
            loc = Loc.make(title=extra + title, href=permalink)
            # TODO created_utc only makes sense for submissions and comments.. upvoted/downvoted/saved should be handled via reddit provider?
            dt = datetime.fromtimestamp(value['created_utc'], tz=pytz.utc)

            links = set()
            for lk in ('link_permalink', 'url'):
                if lk in value:
                    vlk = value[lk]
                    if not vlk.endswith(pl_suffix): # hacky way of handling reddit.com vs www.reddit.com... maybe we should canonify earlier...
                        links.add(vlk)
            links.add(permalink)

            self.items.extend((link, title, loc, dt) for link in links)

            # TODO can both be present? maybe coalesce should assert that..
            body = dcoalesce(value, 'selftext', 'body')
            for u in extract_urls(body):
                self.items.append((u, title, loc, dt))

            return JsonProcessor.SKIP
        if path_matches(kp, ('subreddits', int)):
            title = value['url'] + ' subreddit'
            permalink = reddit_link(value['url'])
            loc = Loc.make(title=title, href=permalink)
            dt = datetime.fromtimestamp(value['created_utc'], tz=pytz.utc)

            cands = [value['public_description'], value['submit_text']]
            for cand in cands:
                for u in extract_urls(cand):
                    self.items.append((u, title, loc, dt))
            return JsonProcessor.SKIP

    def handle_str(self, value: str, path: JPath):
        urls = extract_urls(value)
        if len(urls) == 0:
            return

        kp = self.kpath(path)
        spath = '::'.join(str(x) for x in self.kpath(path))

        for u in urls:
            # TODO propagate Res or something like that?
            self.logger.warning('unexpected url %s at path %s', u, spath)


def collect_reddit(js):
    logger = get_logger()

    def reddit_link(rest: str) -> str:
        return f'https://reddit.com{rest}'

    # TODO need to collect errors here as well? 
    items = [] # type: ignore

    p = Proc()
    p.run(js)
    return p.items
