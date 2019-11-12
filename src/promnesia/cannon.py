#!/usr/bin/env python3
"""
Experimental libarary for normalising domain names and urls to achieve 'canonical' urls for content.
E.g. 
 https://mobile.twitter.com/demarionunn/status/928409560548769792
and
 https://twitter.com/demarionunn/status/928409560548769792
are same content, but you can't tell that by URL equality. Even canonical urls are different!

Also some experiments to establish 'links' hierarchy.
"""
import re
import typing
from typing import Iterable, NamedTuple, Set, Optional, List

import urllib.parse
from urllib.parse import urlsplit, parse_qsl, urlunsplit, parse_qs, urlencode, SplitResult

# this has some benchmark, but quite a few librarires seem unmaintained, sadly
# I guess i'll stick to default for now, until it's a critical bottleneck
# https://github.com/commonsearch/urlparse4
# rom urllib.parse import urlparse

# TODO perhaps archive.org contributes to both?

def try_cutl(prefix, s):
    if s.startswith(prefix):
        return s[len(prefix):]
    else:
        return s

def try_cutr(suffix, s):
    if s.endswith(suffix):
        return s[:-len(suffix)]
    else:
        return s

dom_subst = [
    ('m.youtube.'     , 'youtube.'),
    ('studio.youtube.', 'youtube.'),

    ('mobile.twitter.', 'twitter.'),
    ('m.twitter.'     , 'twitter.'),

    ('m.reddit.'      , 'reddit.'),
    ('old.reddit.'    , 'reddit.'),
    ('i.reddit.'      , 'reddit.'),
    ('pay.reddit.'    , 'reddit.'),
    ('np.reddit.'     , 'reddit.'),

    ('m.facebook.'    , 'facebook.'),
]

def canonify_domain(dom: str):
    # TODO perhaps not necessary now that I'm checking suffixes??
    for st in ('www.', 'amp.'):
        dom = try_cutl(st, dom)

    for start, repl in dom_subst:
        if dom.startswith(start):
            dom = repl + dom[len(start):]
            break

    return dom



default_qremove = {
    'utm_source',
    'utm_campaign',
    'utm_content',
    'utm_medium',
    'utm_term',
    'utm_umg_et',

    # https://moz.com/blog/decoding-googles-referral-string-or-how-i-survived-secure-search
    # some google referral
    'usg',

    # google language??
    'hl',
    'vl',

    # e.g. on github
    'utf8',
}


# TODO perhaps, decide if fragment is meaningful (e.g. wiki) or random sequence of letters?
class Spec(NamedTuple):
    qkeep  : Optional[Set[str]] = None
    qremove: Optional[Set[str]] = None
    fkeep  : bool = False

    def keep_query(self, q: str) -> bool:
        # by default drop all, only do something special in case of specs present
        # it's better choice for default since if it's too unified user would notice it, but not vice versa
        if self.qkeep is None and self.qremove is None:
            return False

        qremove = default_qremove.union(self.qremove or {})

        keep = False
        remove = False
        # pylint: disable=unsupported-membership-test
        if self.qkeep is not None and q in self.qkeep:
            keep = True
        # pylint: disable=unsupported-membership-test
        if q in qremove:
            remove = True
        if keep and remove:
            return True # TODO need a warning
        if keep:
            return True
        if remove:
            return False
        return True
        # TODO basically, at this point only qremove matters

    @classmethod
    def make(cls, **kwargs):
        return cls(**kwargs)

S = Spec.make

# TODO perhaps these can be machine learnt from large set of urls?
specs = {
    'youtube.com': S(
        # TODO search_query?
        qkeep={
            'list', # TODO hmm. list is kinda important for playlist urls...
            'v',
        }, # TODO FIXME frozenset
        qremove={
            't', # TODO not so sure about it


            'time_continue', 'index', 'feature', 'lc', 'app', 'start_radio', 'pbjreload', 'annotation_id',
            'flow', 'sort', 'view',
            'enablejsapi', 'wmode', 'html5', 'autoplay', 'ar',

            'gl', # gl=GB??
            'sub_confirmation', 'shelf_id', 'disable_polymer', 'spfreload', 'src_vid', 'origin', 'rel', 'shuffle',
            'nohtml5',
            'showinfo', 'ab_channel', 'start', 'ebc', 'ref', 'view_as', 'fr', 'redirect_to_creator',
            'sp', # TODO ??
            'noapp', 'client', 'sa', 'ob', 'fbclid', 'noredirect', 'zg_or', 'ved',
        } # TODO not so sure about t
    ),
    # TODO shit. for playlist don't need to remove 'list'...


    'github.com': S(
        qkeep={'q'},
        qremove={'o', 's', 'type', 'tab', 'code', 'privacy', 'fork'},
    ),
    'facebook.com': S(
        qkeep={'fbid', 'story_fbid'},
        qremove={
            'set', 'type', 'fref', 'locale2', '__tn__', 'notif_t', 'ref', 'notif_id', 'hc_ref', 'acontext', 'multi_permalinks', 'no_hist', 'next', 'bucket_id',
            'eid',
            'tab', 'active_tab',

            'source', 'tsid', 'refsrc', 'pnref', 'rc', '_rdr', 'src', 'hc_location', 'section', 'permPage', 'soft', 'pn_ref', 'action',
            'ti', 'aref', 'event_time_id', 'action_history', 'filter', 'ref_notif_type', 'has_source', 'source_newsfeed_story_type',
            'ref_notif_type',
        },
    ),
    'physicstravelguide.com': S(fkeep=True), # TODO instead, pass fkeep marker object for shorter spec?
    'wikipedia.org': S(fkeep=True),
    'scottaaronson.com'  : S(qkeep={'p'}, qremove={}, fkeep=True),
    'urbandictionary.com': S(qkeep={'term'}, qremove={}),
    'ycombinator.com'    : S(qkeep={'id'}, qremove={}),
    'play.google.com'    : S(qkeep={'id'}, qremove={}),
    'answers.yahoo.com'  : S(qkeep={'qid'}, qremove={}),
}

_def_spec = S()
# TODO use cache?
def get_spec(dom: str) -> Spec:
    # ugh. a bit ugly way of getting stuff without subdomain...
    parts = dom.split('.')
    cur = None
    for p in reversed(parts):
        if cur is None:
            cur = p
        else:
            cur = p + '.' + cur
        sp = specs.get(cur)
        if sp is not None:
            return sp
    return _def_spec

class CanonifyException(Exception):
    pass

# TODO not so sure if it's better to quote or not?
quote_via   = urllib.parse.quote
unquote_via = urllib.parse.unquote


def _quote_path(path: str) -> str:
    parts = path.split('/')
    nparts = []
    for p in parts:
        # TODO maybe re.match?
        if '%' in p or '+' in p: # some urls are partially encoded... perhaps canonify needs hints indicating if url needs normalising or not
            p = unquote_via(p)
        # TODO safe argumnet?
        nparts.append(quote_via(p))
    return '/'.join(nparts)


def _prenormalise(url: str) -> str:
    # meh..
    url = re.sub(r'google\..*/amp/s/', '', url)

    if '?' not in url:
        # sometimes urls have not ? but do have query parameters starting with & for some reason; urlsplit chokes over it
        # e.g. in google takeout
        # not sure how safe it in general...
        first_q = url.find('&')
        if first_q != -1:
            return url[:first_q] + '?' + url[first_q + 1:]
    return url


def transform_split(split: SplitResult):
    netloc = canonify_domain(split.netloc)

    path     = split.path
    qparts   = parse_qsl(split.query)

    fragment = split.fragment


    ID   = r'(?P<id>[^/]+)'
    REST = r'(?P<rest>.*)'
    rules = {
        # TODO m. handling might be quite common
        # f'm.youtube.com/{REST}': ('youtube.com', '{rest}'),
        (
            f'youtu.be/{ID}',
            f'youtube.com/embed/{ID}',
        ) : ('youtube.com', '/watch', 'v={id}'),
        # TODO wonder if there is a better candidate for canonical video link?
        # {DOMAIN} pattern? implicit?
    }

    def iter_rules():
        for fr, to in rules.items():
            if isinstance(fr, str):
                fr = (fr, )
            for f in fr:
                yield f, to

    for fr, to in iter_rules():
        # TODO precache by domain?
        dom, rest = fr.split('/', maxsplit=1)
        if dom != netloc:
            continue

        rest = '/' + rest  # path seems to always start with /
        m = re.fullmatch(rest, path)
        if m is None:
            continue
        gd = m.groupdict()
        if len(to) == 2:
            to = to + ('', )

        (netloc, path, qq) = [t.format(**gd) for t in to]
        qparts.extend(parse_qsl(qq)) # TODO hacky..
        break


    return netloc, path, qparts, fragment


# TODO ok, I suppose even though we can't distinguish + and space, likelihood of them overlapping in normalised url is so low, that it doesn't matter much
# TODO actually, might be easier for most special charaters
def canonify(url: str) -> str:
    # TODO check for invalid charaters?
    url = _prenormalise(url)

    try:
        # TODO didn't really get difference from urlparse
        parts = urlsplit(url)
    except Exception as e:
        raise CanonifyException(url) from e

    # TODO move to prenormalise?
    if parts.scheme == '':
        # if scheme is missing it doesn't parse netloc properly...
        try:
            parts = urlsplit('http://' + url)
        except Exception as e:
            raise CanonifyException(url) from e


    domain, path, qq, _frag = transform_split(parts)

    spec = get_spec(domain)


    # TODO FIXME turn this logic back on?
    # frag = parts.fragment if spec.fkeep else ''
    frag = ''

    qq = [(k, v) for k, v in qq if spec.keep_query(k)]
    qq = list(sorted(qq)) # order matters in theory, but definitely not by default
    # TODO still not sure what we should do..
    # quote_plus replaces %20 with +, not sure if we want it...
    query = urlencode(qq, quote_via=quote_via)

    path = _quote_path(path)

    uns = urlunsplit((
        '',
        domain,
        path,
        query,
        frag,
    ))

    uns = try_cutl('//', uns)  # // due to dummy protocol
    uns = try_cutr('/', uns) # not sure if there is a better way
    return uns

# TODO should actually understand 'sequences'?
# e.g.
# https://www.scottaaronson.com/blog/?p=3167#comment-1731882 is kinda hierarchy of scottaaronson.com, post 3167 and comment 1731882
# but when working with it from server, would be easier to just do multiple queries I guess..
# https://www.scottaaronson.com/blog/?p=3167 is kind ahierarchy of scottaaronson.com ; 


import pytest # type: ignore



# https://youtu.be/iCvmsMzlF7o

@pytest.mark.parametrize('url,expected', [
    ( "https://www.youtube.com/watch?v=1NHbPN9pNPM&index=63&list=WL&t=491s"
    , "youtube.com/watch?list=WL&v=1NHbPN9pNPM" # TODO not so sure about &t, it's sort of useful
    ),
    ( "youtube.com/watch?v=wHrCkyoe72U&feature=share&time_continue=6"
    , "youtube.com/watch?v=wHrCkyoe72U"
    ),

    ( "youtube.com/embed/nyc6RJEEe0U?feature=oembed"
    , "youtube.com/watch?v=nyc6RJEEe0U"
    ),

    # TODO hmm. ordering?
    ( 'https://youtu.be/iCvmsMzlF7o?list=WL'
    , 'youtube.com/watch?list=WL&v=iCvmsMzlF7o'
    ),

    # TODO can even be like that or contain timestamp (&t=)
    # TODO warn if param already present? shouldn't happen..

    # TODO could be interesting to do automatic rule extraction by querying one represnetative and then extracting canonical

    # TODO national domains don't matter for youtube

    # [*, 'youtube', ANY_DOMAIN] / 'embed' -> 'youtube.com/watch'
    # TODO use regex backrefs?
    #

    ( "m.youtube.com/watch?v=Zn6gV2sdl38"
    , "youtube.com/watch?v=Zn6gV2sdl38"
    ),

    # ( "https//youtube.com/playlist?list=PLeOfc0M-50LmJtZwyOfw6aVopmIbU1t7t"
    # , "youtube.com/playlist?list=PLeOfc0M-50LmJtZwyOfw6aVopmIbU1t7t"
    # ),
    # TODO perhaps it should result in video link + sibling link?
    # when exploring other people's playlists this could be quite useful?

    # ( "https://www.youtube.com/watch?v=1NHbPN9pNPM&index=63&list=WL&t=491s"
    # , "youtube.com/watch?v=1NHbPN9pNPM&list=WL" # TODO not so sure about &t, it's sort of useful
    # ),
    # TODO
    # youtube.com/user/magauchsein/playlists?sort=dd&view=50&shelf_id=14
    # youtube.com/user/TheChemlife/videos?view=0&sort=p&flow=grid
])
def test_youtube(url, expected):
    assert canonify(url) == expected


@pytest.mark.parametrize('url, expected', [
    ( 'https://www.reddit.com/r/firefox/comments/bbugc5/firefox_bans_free_speech_commenting_plugin/?ref=readnext'
    , 'reddit.com/r/firefox/comments/bbugc5/firefox_bans_free_speech_commenting_plugin',
    ),

    ( 'https://www.reddit.com/r/selfhosted/comments/8j8mo3/what_are_you_self_hosting/dz19gh9/?utm_content=permalink&utm_medium=user&utm_source=reddit&utm_name=u_karlicoss'
    , 'reddit.com/r/selfhosted/comments/8j8mo3/what_are_you_self_hosting/dz19gh9',
    )
    # TODO hmm. parent relationship can just rely on urls for reddit
    # just need to support it in server I suppose

    # TODO search queries?
    # https://www.reddit.com/search?q=AutoValue

    # TODO def need better markdown handling
    # https://reddit.com/r/intj/comments/cmof04/me_irl/ew4a3dw/][    Me_irl]  
    # reddit.com/r/intj/comments/cmof04/me_irl/ew4a3dw/%5D%5BMe_irl%5D



])
def test_reddit(url, expected):
    assert canonify(url) == expected

@pytest.mark.parametrize("url,expected", [
    # TODO FIXME fragment handling
    # ( "https://www.scottaaronson.com/blog/?p=3167#comment-1731882"
    # , "scottaaronson.com/blog/?p=3167#comment-1731882"
    # ),


    # TODO FIXME fragment handling
    # ( "https://en.wikipedia.org/wiki/tendon#cite_note-14"
    # , "en.wikipedia.org/wiki/tendon#cite_note-14"
    # ),

    # TODO FIXME fragment handling
    # ( "https://physicstravelguide.com/experiments/aharonov-bohm#tab__concrete"
    # , "physicstravelguide.com/experiments/aharonov-bohm#tab__concrete"
    # ),

    ( "https://github.com/search?o=asc&q=track&s=stars&type=Repositories"
    , "github.com/search?q=track"
    ),
    ( "https://80000hours.org/career-decision/article/?utm_source=The+EA+Newsletter&utm_campaign=04ca3c2244-EMAIL_CAMPAIGN_2019_04_03_04_26&utm_medium=email&utm_term=0_51c1df13ac-04ca3c2244-318697649"
    , "80000hours.org/career-decision/article"
    ),
    ( "https://www.facebook.com/photo.php?fbid=24147689823424326&set=pcb.2414778905423667&type=3&theater"
    , "facebook.com/photo.php?fbid=24147689823424326"
    ),
    ( "https://play.google.com/store/apps/details?id=com.faultexception.reader&hl=en"
    , "play.google.com/store/apps/details?id=com.faultexception.reader"
    ),
    # TODO it also got &p= parameter, which refers to page... not sure how to handle this
    # news.ycombinator.com/item?id=15451442&p=2
    ( "https://news.ycombinator.com/item?id=12172351"
    , "news.ycombinator.com/item?id=12172351"
    ),
    ( "https://urbandictionary.com/define.php?term=Belgian%20Whistle"
    , "urbandictionary.com/define.php?term=Belgian%20Whistle"
    ),
    ( "https://en.wikipedia.org/wiki/Dinic%27s_algorithm"
    , "en.wikipedia.org/wiki/Dinic%27s_algorithm"
    ),

    ( "zoopla.co.uk/to-rent/details/42756337#D0zlBWeD4X85odsR.97"
    , "zoopla.co.uk/to-rent/details/42756337"
    ),

    ( "withouthspec.co.uk/rooms/16867952?guests=2&adults=2&location=Berlin%2C+Germany&check_in=2017-08-16&check_out=2017-08-20"
    , "withouthspec.co.uk/rooms/16867952"
    ),

    ( "amp.theguardian.com/technology/2017/oct/09/mark-zuckerberg-facebook-puerto-rico-virtual-reality"
    , "theguardian.com/technology/2017/oct/09/mark-zuckerberg-facebook-puerto-rico-virtual-reality",
    ),

    ( "https://answers.yahoo.com/question/index?qid=20071101131442AAk9bGp"
    , "answers.yahoo.com/question/index?qid=20071101131442AAk9bGp"
    ),
    ( "flowingdata.com/2010/12/14/10-best-data-visualization-projects-of-the-year-%e2%80%93-2010"
    , "flowingdata.com/2010/12/14/10-best-data-visualization-projects-of-the-year-%E2%80%93-2010"
    ),
    ( "flowingdata.com/2010/12/14/10-best-data-visualization-projects-of-the-year-–-2010"
    , "flowingdata.com/2010/12/14/10-best-data-visualization-projects-of-the-year-%E2%80%93-2010"
    ),

    ( "https://spoonuniversity.com/lifestyle/marmite-ways-to-eat-it&usg=AFQjCNH4s1SOEjlpENlfPV5nuvADZpSdow"
    , "spoonuniversity.com/lifestyle/marmite-ways-to-eat-it"
    ),

    ( 'https://google.co.uk/amp/s/amp.reddit.com/r/androidapps/comments/757e2t/swiftkey_or_gboard'
    , 'reddit.com/r/androidapps/comments/757e2t/swiftkey_or_gboard'
    ),

    # should sort query params
    ( 'https://www.youtube.com/watch?v=hvoQiF0kBI8&list=WL&index=2'
    , 'youtube.com/watch?list=WL&v=hvoQiF0kBI8',
    ),
    ( 'https://www.youtube.com/watch?list=WL&v=hvoQiF0kBI8&index=2'
    , 'youtube.com/watch?list=WL&v=hvoQiF0kBI8',
    )

    # ( "gwern.net/DNB+FAQ"
    # , "TODO" # ???
    # ),

    # TODO shit. is that normal??? perhaps need to manually move fragment?
    # SplitResult(scheme='https', netloc='unix.stackexchange.com', path='/questions/171603/convert-file-contents-to-lower-case/171708', query='', fragment='171708&usg=AFQjCNEFCGqCAa4P4Zlu2x11bThJispNxQ')
    # ( "https://unix.stackexchange.com/questions/171603/convert-file-contents-to-lower-case/171708#171708&usg=AFQjCNEFCGqCAa4P4Zlu2x11bThJispNxQ"
    # , "unix.stackexchange.com/questions/171603/convert-file-contents-to-lower-case/171708#171708"
    # )
])
def test(url, expected):
    assert canonify(url) == expected
    # TODO github queries
# github.com/search?l=Python&q=reddit+backup
# github.com/search?p=3&q=ipynb+language%3AHaskell
# github.com/search?q=kobo+ExtraData
# github.com/search?q=what-universal-human-experiences-are-you-missing-without-realizing-it

    # TODO git+https://github.com/expectocode/telegram-export@master
    # TODO  again, for that actually sequence would be good...

    # TODO "https://twitter.com/search?q=pinboard search&src=typd"

    # TODO https://www.zalando-lounge.ch/#/
    # TODO m.facebook.com
    # TODO         [R('^(youtube|urbandictionary|tesco|scottaaronson|answers.yahoo.com|code.google.com)') , None],



    # TODO
# amazon.co.uk/gp/offer-listing/B00525XKL4/ref=dp_olp_new
# amazon.co.uk/gp/offer-listing/B00525XKL4/ref=olp_twister_child

    # TODO 
    # en.wikipedia.org/wiki/S&P_500_Index


    # TODO
    # google.co.uk/maps/place/Hackney+Bureau/@51.5293789,-0.0527919,16.88z/data=!bla-bla!-bla


    # TODO 
    # perhaps, disable utf8 everywhere?
    # github.com/search?utf8=%E2%9C%93&q=%22My+Clippings.txt%22

    # TODO FIXME fragment handling
    # ( "https://www.scottaaronson.com/blog/?p=3167#comment-1731882"
    # , "scottaaronson.com/blog/?p=3167#comment-1731882"
    # ),

@pytest.mark.parametrize("urls", [
    {
        "launchpad.net/ubuntu/%2Bsource/okular",
        "launchpad.net/ubuntu/+source/okular",
    },
    {
        "flowingdata.com/2010/12/14/10-best-data-visualization-projects-of-the-year-–-2010",
        "flowingdata.com/2010/12/14/10-best-data-visualization-projects-of-the-year-%e2%80%93-2010",
        "https://flowingdata.com/2010/12/14/10-best-data-visualization-projects-of-the-year-%e2%80%93-2010/&usg=AFQjCNEZsEGz9rqpWqlFXR5Tc7pkCKY5sQ",
    },
])
def test_same_norm(urls):
    urls = list(sorted(urls))
    u0 = urls[0]
    c0 = canonify(u0)
    for u in urls[1:]:
        c = canonify(u)
        assert c0 == c, f'Expected {u0} and {u} to be same canonically; got {c0} and {c} instead'

def test_error():
    # canonify('  +74Zo535, fewfwf@gmail.com') # -- apparently was patched in some python3.7 versions
    with pytest.raises(CanonifyException):
        # borrowed from https://bugs.mageia.org/show_bug.cgi?id=24640#c7
        canonify('https://example.com\uFF03@bing.com')


# TODO chrome-extension://fdpohaocaechififmbbbbbknoalclacl ??
# /L/data/wereyouhere/intermediate  ✔  rg 'orig_url.*#' 20190519090753.json | grep -v zoopla | grep -v 'twitter' | grep -v youtube

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('input', nargs='?')
    p.add_argument('--human', action='store_true')
    p.add_argument('--groups', action='store_true')
    p.add_argument('--domains', action='store_true')
    args = p.parse_args()

    it: Iterable[str]
    if args.input is None:
        import sys
        it = sys.stdin
    else:
        it = [args.input]

    if args.groups:
        groups(it, args)
    if args.domains:
        domains(it)
    else:
        display(it, args)


 # TODO wonder if lisp could be convenient for this. lol
TW_PATTERNS = [
    {
        'U': r'[\w-]+',
        'S': r'\d+',
        'L': r'[\w-]+',
    },

    r'twitter.com/U/status/S',
    r'twitter.com/U/status/S/retweets',
    r'twitter.com/statuses/S',
    r'twitter.com/U',
    r'twitter.com/U/likes',
    r'twitter.com/U/status/S/.*',
    r'twitter.com/U/statuses/S',
    r'twitter.com/i/notifications',
    r'twitter.com/U/with_replies',
    r'twitter.com/(settings|account)/.*',
    r'twitter.com/U/lists',
    r'twitter.com/U/lists/L(/.*)?',
    r'twitter.com/i/web/status/S',
    r'twitter.com',
    r'tweetdeck.twitter.com',
    r'twitter.com/U/(media|photo|followers|following)',
    # r'mobile.twitter.com/.*',

    r'twitter.com/compose/tweet',
    r'twitter.com/hashtag/\w+',
    r'twitter.com/i/(moments|offline|timeline|u|bookmarks|display|redirect)',
    r'twitter.com/intent/tweet.*',
    r'twitter.com/lists/(create|add_member)',
    r'twitter.com/search-home',
    r'twitter.com/notifications/\d+',

    r'twitter.com/i/events/\d+',

    r'(dev|api|analytics|developer|help|support|blog|anywhere|careers|pic).twitter.com/.*',
]

RD_PATTERNS = [
    {
        'U'  : r'[\w-]+',
        'S'  : r'\w+',
        'PID': r'\w+',
        'PT' : r'\w+',
        'CID': r'\w+',
    },
    r'reddit.com/(user|u)/U',
    r'reddit.com/user/U/(comments|saved|posts)',
    r'reddit.com/r/S(/(top|new|hot|about|search|submit|rising))?',
    r'reddit.com/r/S/comments/PID/PT',
    r'reddit.com/r/S/duplicates/PID/PT',
    r'reddit.com/r/S/comments/PID/PT/CID',
    r'reddit.com/r/S/wiki(/.*)?',

    r'reddit.com/comments/PID',
    r'reddit.com/(subreddits|submit|search|top|original|premium|gilded|gold|gilding)',
    r'reddit.com/subreddits/mine',
    r'reddit.com',
    r'reddit.com/(settings|prefs)(/.*)?',
    r'reddit.com/message/(unread|inbox|messages|compose|sent|newsletter)',
    r'reddit.com/me/.*',
    r'reddit.com/login',

    r'ssl.reddit.com/api/v1/authorize',
    r'reddit.com/dev/api',
    r'reddit.com/api/v1/authorize',
    r'reddit.com/domain/.*',
]

GH_PATTERNS = [
    {
        'U': r'[\w-]+',
        'R': r'[\w\.-]+',
        'b': r'[\w-]+',
        'X': r'(/.*)?',
        'C': r'\w+',
        'G': r'\w+',
    },
    r'github.com/U',
    r'github.com/U/R(/(watchers|settings|actions|branches))?',
    r'github.com/U/R/wiki/.*',
    r'github.com/U/R/issuesX',
    r'github.com/U/R/issues\?q.*',
    r'github.com/U/R/networkX',
    r'github.com/U/R/releasesX',
    r'github.com/U/R/blobX',
    r'github.com/U/R/treeX',
    r'github.com/U/R/pullX',
    r'github.com/U/R/pulls',
    r'github.com/U/R/wiki',
    r'github.com/U/R/commits/B',
    r'github.com/U/R/commit/C',
    r'github.com/U/R/search\?.*',
    r'github.com/search\?.*',
    r'github.com/search/advanced\?.*',
    r'github.com/loginX',
    r'github.com/settings/.*',
    r'github.com/\?q.*',

    r'github.com/_google_extract.*', # TODO wtf?
    r'github.communityX',
    r'github.com/dashboard',
    r'help.github.comX',
    r'gist.github.com/UX',
    r'gist.github.com/G',
    r'developer.github.com/.*',

    # TODO FIXME no canonical here
    # https://gist.github.com/dneto/2258454
    # same as https://gist.github.com/2258454
]

YT_PATTERNS = [
    {
        'V': r'[\w-]+',
        'L': r'[\w-]+',
        'U': r'[\w-]+',
        'C': r'[\w-]+',
    },
    r'youtube.com/watch\?v=V',
    r'youtube.com/watch\?list=L&v=V',
    r'youtube.com/watch\?list=L',
    r'youtube.com/playlist\?list=L',
    r'youtube.com/user/U(/(videos|playlists|feautred|channels|featured))?',
    r'youtube.com/(channel|c)/C(/(videos|playlists))?',

    r'accounts.youtube.com/.*',
    r'youtube.com/signin\?.*',
    r'youtube.com/redirect\?.*',
    r'youtube.com/results\?(search_query|q)=.*',
    r'youtube.com/feed/(subscriptions|library|trending|history)',
    r'youtube.com',
    r'youtube.com/(post_login|upload)',
]

SOP = r'(^|\w+\.)stackoverflow.com'

SO_PATTERNS = [
    {
        # TODO just replace with identifier? should be quite unambiguous
        'QI': r'\d+',
        'QT': r'[\w-]+',
        'A' : r'\d+',
        'UI': r'\d+',
        'U' : r'[\w-]+',
    },
    SOP + r'/questions/QI/QT',
    SOP + r'/questions/QI/QT/A',
    SOP + r'/q/QI',
    SOP + r'/q/QI/A',
    SOP + r'/a/QI',
    SOP + r'/a/QI/A',
    SOP + r'/search',
    SOP + r'/users/UI',
    SOP + r'/users/UI/U',
    SOP,
]

WKP = r'(^|.+\.)wikipedia.org'

WK_PATTERNS = [
    {
        'AN': r'[\w%.-]+',
    },
    WKP + '/wiki/AN',
    WKP,
]

FB_PATTERNS = [
    {
        'F': 'facebook.com',
        'U': r'[\w\.-]+',
        'P': r'\d+',
        'I': r'\d+',
        'CI': r'\d+',
    },
    r'F',
    r'F/U',
    r'F/U/(posts|videos)/P',
    r'F/U/posts/P\?comment_id=CI',
    r'F/photo.php\?fbid=I',
    r'F/photo.php\?fbid=I&id=I',
    r'F/profile.php\?fbid=I',
    r'F/profile.php\?id=I',
    r'F/groups/U',
    r'F/search/.*',
    r'F/events/I',
    r'F/events/I/permalink/I',
    r'F/events/I/I',
    r'F/U/photos/pcb.I/I',

    r'F/pages/U/P',
    r'F/stories/I',
    r'F/notes/U/P',
]

PATTERNS = {
    'twitter'   : TW_PATTERNS,
    'reddit'    : RD_PATTERNS,
    'github.com': GH_PATTERNS,
    'youtube'   : YT_PATTERNS,
    'stackoverflow': SO_PATTERNS,
    'facebook'  : FB_PATTERNS,
    'wikipedia' : WK_PATTERNS,
}


def get_patterns():
    def repl(p, dct):
        for k, v in dct.items():
            p = p.replace(k, v)
        # TODO FIXME unreplaced upper?
        return p

    def handle(stuff):
        pats = []
        repls = []
        for x in stuff:
            if isinstance(x, dict):
                repls.append(x)
            else:
                pats.append(x)
        if len(repls) == 0:
            repls.append({})
        [rdict] = repls
        for p in pats:
            yield repl(p, rdict)
    return {k: list(handle(v)) for k, v in PATTERNS.items()}


def domains(it):
    from collections import Counter
    c: typing.Counter[str] = Counter()
    for line in it:
        url = line.strip()
        try:
            nurl = canonify(url)
        except CanonifyException as e:
            print(f"ERROR while normalising! {nurl} {e}")
            c['ERROR'] += 1
            continue
        else:
            udom = nurl[:nurl.find('/')]
            c[udom] += 1
    from pprint import pprint
    pprint(c.most_common(20))


def groups(it, args):
    all_pats = get_patterns()

    from collections import Counter
    c: typing.Counter[Optional[str]] = Counter()
    unmatched: List[str] = []

    def dump():
        print(c)
        print('   ' + str(unmatched[-10:]))

    def reg(url, pat):
        c[pat] += 1
        if pat is None:
            unmatched.append(nurl)


    for i, line in enumerate(it):
        if i % 10000 == 0:
            pass
            # dump()
        url = line.strip()
        try:
            nurl = canonify(url)
        except CanonifyException as e:
            print(f"ERROR while normalising! {nurl} {e}")
            continue
        udom = nurl[:nurl.find('/')]
        usplit = udom.split('.')
        patterns = None
        for dom, pats in all_pats.items():
            dsplit = dom.split('.')
            if '$'.join(dsplit) in '$'.join(usplit): # meh
                patterns = pats
                break
        else:
            # TODO should just be ignored?
            # reg(nurl, None)
            continue

        pat = None
        for p in patterns:
            m = re.fullmatch(p, nurl)
            if m is None:
                continue
            pat = p
            break
        reg(nurl, pat)
    for u in sorted(unmatched):
        print(u)
    dump()
    nones = c[None]
    # TODO print link examples alongside?
    print(f"Unmatched: {nones / sum(c.values()) * 100:.1f}%")
    uc = Counter([u.split('/')[:2][-1] for u in unmatched]).most_common(10)
    from pprint import pprint
    pprint(uc)


def display(it, args): # TODO better name?
    import difflib
    # pylint: disable=import-error
    from termcolor import colored as C # type: ignore
    from sys import stdout

    for line in it:
        line = line.strip()
        if args.human:
            print('---')
            print(line)
        can = canonify(line)
        # TODO use textual diff?
        sm = difflib.SequenceMatcher(None, line, can)

        org_ = ""
        can_ = ""

        pr = False
        def delete(x):
            nonlocal pr
            if x in (
                    'https://www.',
                    'http://www.',
                    'http://',
                    'https://',
                    'file://',
                    '/',
            ):
                col = None
            else:
                if len(x) > 0:
                    pr = True
                col = 'red'
            return C(x, color=col)

        for what, ff, tt, ff2, tt2 in sm.get_opcodes():
            if what == 'delete':
                fn = delete
            elif what == 'equal':
                fn = lambda x: C(x, color=None)
            else:
                pr = True
                fn = lambda x: C(x, color='cyan')
            # TODO exclude certain items from comparison?


            org_ += fn(line[ff: tt])
            can_ += fn(can[ff2: tt2])
            cl = max(len(org_), len(can_))
            org_ += ' ' * (cl - len(org_))
            can_ += ' ' * (cl - len(can_))

        if pr:
            stdout.write(f'{org_}\n{can_}\n---\n')


if __name__ == '__main__':
    main()

# TODO hmm, it's actually sort of fingerprinter... so maybe that's what I should call it

# tweet          -P-> user (not always possible to determine)
# reddit comment -P-> reddit post
# reddit post    -P-> subreddit
# YT video       -P-> user, playlist

# wikipedia footnote will have ???
# certain urls would need to treat # as parent relationship (e.g. slatestarcodex?)

# siblings are items that share a parent (could also return which one is shared)

# youtube end domain normalising: very few occurences, so I won't care about them for now


# TODO for debugging, have special mode that only uses query param trimming one by one

# TODO running comparison:
# sqlite3 /L/data/promnesia/promnesia.sqlite 'select distinct orig_url from visits where norm_url like "%twitter%" order by orig_url' | src/promnesia/cannon.py

# TODO sqlite3 /L/data/promnesia/promnesia.sqlite 'select orig_url from visits' | src/promnesia/cannon.py --domains
# TODO show percents?
