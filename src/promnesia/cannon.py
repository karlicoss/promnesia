#!/usr/bin/env python3
"""
Experimental libarary for normalising domain names and urls to achieve 'canonical' urls for content.
E.g.
 https://mobile.twitter.com/demarionunn/status/928409560548769792
and
 https://twitter.com/demarionunn/status/928409560548769792
are same content, but you can't tell that by URL equality. Even canonical urls are different!

Also some experiments to establish 'URL hierarchy'.
"""
# TODO eh?? they fixed mobile.twitter.com?

from itertools import chain
import re
import typing
from typing import Iterable, NamedTuple, Set, Optional, List, Sequence, Union, Tuple, Dict, Any, Collection

import urllib.parse
from urllib.parse import urlsplit, parse_qsl, urlunsplit, parse_qs, urlencode, SplitResult


# this has some benchmark, but quite a few librarires seem unmaintained, sadly
# I guess i'll stick to default for now, until it's a critical bottleneck
# https://github.com/commonsearch/urlparse4
# rom urllib.parse import urlparse

# TODO perhaps archive.org contributes to both?

def try_cutl(prefix: str, s: str) -> str:
    if s.startswith(prefix):
        return s[len(prefix):]
    else:
        return s

def try_cutr(suffix: str, s: str) -> str:
    if s.endswith(suffix):
        return s[:-len(suffix)]
    else:
        return s

# TODO move this to site-specific normalisers?
dom_subst = [
    ('m.youtube.'     , 'youtube.'),
    ('studio.youtube.', 'youtube.'),

    ('mobile.twitter.', 'twitter.'),
    ('m.twitter.'     , 'twitter.'),
    ('nitter.net'     , 'twitter.com'),

    ('m.reddit.'      , 'reddit.'),
    ('old.reddit.'    , 'reddit.'),
    ('i.reddit.'      , 'reddit.'),
    ('pay.reddit.'    , 'reddit.'),
    ('np.reddit.'     , 'reddit.'),

    ('m.facebook.'    , 'facebook.'),
    # app.getpocket.com is the canonical domain in the JSON returned by
    # https://github.com/karlicoss/pockexport, so let's canonicalize to that.
    ('getpocket.'     , 'app.getpocket.'),
]

def canonify_domain(dom: str) -> str:
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

default_qkeep = [
    # ok, various BBS have it, hackernews has it etc?
    # hopefully it's a reasonable one to keep..
    'id',

    # common to forums, usually means 'thread'
    't',

    # common to some sites.., usually 'post'
    'p',
]

# TODO perhaps, decide if fragment is meaningful (e.g. wiki) or random sequence of letters?
class Spec(NamedTuple):
    qkeep  : Optional[Union[Collection[str], bool]] = None
    qremove: Optional[Set[str]] = None
    fkeep  : bool = False

    def keep_query(self, q: str) -> Optional[int]: # returns order
        if self.qkeep is True:
            return 1
        qkeep = {
            q: i for i, q in enumerate(chain(default_qkeep, self.qkeep or []))
        }
        qremove = default_qremove.union(self.qremove or {})
        # I suppose 'remove' is only useful for logging. we remove by default anyway

        keep = False
        remove = False
        qk = qkeep.get(q)
        if qk is not None:
            return qk
        # todo later, check if spec tells both to keep and remove?
        if q in qremove:
            return None
        # by default drop all
        # it's a better default, since if it's *too* unified, the user would notice it. but not vice versa!
        return None

    @classmethod
    def make(cls, **kwargs) -> 'Spec':
        return cls(**kwargs)

S = Spec

# TODO perhaps these can be machine learnt from large set of urls?
specs: Dict[str, Spec] = {
    'youtube.com': S(
        # TODO search_query?
        qkeep=[ # note: experimental.. order matters here
            'v',
            't',
            'list',
        ],
        # todo frozenset?
        qremove={
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
    'scottaaronson.com'  : S(qkeep={'p'}, fkeep=True),
    'urbandictionary.com': S(qkeep={'term'}),
    'ycombinator.com'    : S(qkeep={'id'}), # todo just keep id by default?
    'play.google.com'    : S(qkeep={'id'}),
    'answers.yahoo.com'  : S(qkeep={'qid'}),
    'isfdb.org': S(qkeep=True),
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



# ideally we'd just be able to reference the domain name and use it in the subst?
# some sort of hierarchical matchers? not sure what's got better performance..
# if 'from?site=' in url:
#     return p.query('site')

Spec2 = Any # TODO

# TODO this should be a map
Frag = Any
Parts = Sequence[Tuple[str, str]]


def _yc(domain: str, path: str, qq: Parts, frag: Frag) -> Tuple[Any, Any, Parts, Frag]:
    if path[:5] == '/from':
        site = dict(qq).get('site')
        if site is not None:
            domain = site
            path = ''
            qq = ()
            frag = ''
    # TODO this should be in-place? for brevity?
    return (domain, path, qq, frag)

def get_spec2(dom: str) -> Optional[Spec2]:
    return {
        'news.ycombinator.com': _yc,
    }.get(dom)


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


# TODO wtf is it doing???
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
    qparts   = parse_qsl(split.query, keep_blank_values=True)

    fragment = split.fragment

    ID   = r'(?P<id>[^/]+)'
    REST = r'(?P<rest>.*)'

    Left = Union[str, Sequence[str]]
    Right = Tuple[str, str, str]
    # the idea is that we can unify certain URLs here and map them to the 'canonical' one
    # this is a dict only for grouping but should be a list really.. todo
    rules: Dict[Left, Right] = {
        # TODO m. handling might be quite common
        # f'm.youtube.com/{REST}': ('youtube.com', '{rest}'),
        (
            f'youtu.be/{ID}',
            f'youtube.com/embed/{ID}',
        ) : ('youtube.com', '/watch', 'v={id}'),
        # TODO wonder if there is a better candidate for canonical video link?
        # {DOMAIN} pattern? implicit?
        (
            'twitter.com/home',
            'twitter.com/explore',
        ) : ('twitter.com', '', ''),
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
        qparts.extend(parse_qsl(qq, keep_blank_values=True)) # TODO hacky..
        # TODO eh, qparts should really be a map or something...
        break


    return netloc, path, qparts, fragment



def myunsplit(domain: str, path: str, query: str, fragment: str) -> str:
    uns = urlunsplit((
        '', # dummy protocol
        domain,
        path,
        query,
        fragment,
    ))
    uns = try_cutl('//', uns)  # // due to dummy protocol
    return uns



#
# r'web.archive.org/web/\d+/
# def canonify_simple(url: str) -> Optional[str]:
#     '''
#     Experiment with simply using regexes for normalising, as close to regular python as it gets
#     '''
#     # - using named groups for comments?

#     # TODO to be fair, archive.org is a 'very' special case..
#     regexes = [
#         r'web.archive.org/web/(?<timestamp>\d+)/' # TODO what about 'rest'?
#     ]
#     for re in regexes:

def handle_archive_org(url: str) -> Optional[str]:
    are = r'web.archive.org/web/(?P<timestamp>\d+)/(?P<rest>.*)'
    m = re.fullmatch(are, url)
    if m is None:
        return None
    else:
        return m.group('rest')


# TODO ok, I suppose even though we can't distinguish + and space, likelihood of them overlapping in normalised url is so low, that it doesn't matter much
# TODO actually, might be easier for most special charaters
def canonify(url: str) -> str:
    # TODO check for invalid charaters?
    url = _prenormalise(url)

    try:
        # TODO didn't really get difference from urlparse
        parts = urlsplit(url)
    except Exception as e:
        # TODO not sure about the exception...
        # TODO return it instead of raising
        raise CanonifyException(url) from e

    # TODO move to prenormalise?
    if parts.scheme == '':
        # if scheme is missing it doesn't parse netloc properly...
        try:
            parts = urlsplit('http://' + url)
        except Exception as e:
            raise CanonifyException(url) from e

    # meh. figure out what's up with transform_split
    no_protocol = parts.netloc + parts.path + parts.query + parts.fragment

    res = handle_archive_org(no_protocol)
    if res is not None:
        assert len(res) < len(no_protocol) # just a paranoia to avoid infinite recursion...
        return canonify(res)

    domain, path, qq, _frag = transform_split(parts)

    spec2 = get_spec2(domain)
    if spec2 is not None:
        # meh
        domain, path, qq, _frag = spec2(domain, path, qq, _frag)


    spec = get_spec(domain)

    # TODO FIXME turn this logic back on?
    # frag = parts.fragment if spec.fkeep else ''
    frag = ''

    iqq = []
    for k, v in qq:
        order = spec.keep_query(k)
        if order is not None:
            iqq.append((order, k, v))
    qq = [(k, v) for i, k, v in sorted(iqq)]
    # TODO still not sure what we should do..
    # quote_plus replaces %20 with +, not sure if we want it...
    query = urlencode(qq, quote_via=quote_via) # type: ignore[type-var]

    path = _quote_path(path)

    uns = myunsplit(domain, path, query, frag)
    uns = try_cutr('/', uns) # not sure if there is a better way
    return uns


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
    r'twitter.com/home',
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

PKP = r'^(app)?\.getpocket\.com'

PK_PATTERNS = [
    {
        'ID': r'\d+',
    },
    PKP + '/read/ID',
]

# NOTE: right, I think this is just for analysis so far... not actually used
PATTERNS = {
    'twitter'   : TW_PATTERNS,
    'reddit'    : RD_PATTERNS,
    'github.com': GH_PATTERNS,
    'youtube'   : YT_PATTERNS,
    'stackoverflow': SO_PATTERNS,
    'facebook'  : FB_PATTERNS,
    'wikipedia' : WK_PATTERNS,
    'pocket'    : PK_PATTERNS,
    # 'news.ycombinator.com': YC_PATTERNS,
}


def get_patterns():  # pragma: no cover
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


def domains(it): # pragma: no cover
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


def groups(it, args): # pragma: no cover
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



def display(it, args) -> None: # pragma: no cover
    # TODO better name?
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


def main() -> None: # pragma: no cover
    import argparse
    p = argparse.ArgumentParser(epilog='''
- sqlite3 promnesia.sqlite 'select distinct orig_url from visits' | cannon.py --domains

- running comparison
  sqlite3 promnesia.sqlite 'select distinct orig_url from visits where norm_url like "%twitter%" order by orig_url' | src/promnesia/cannon.py
''', formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, width=100) # type: ignore
    )
    p.add_argument('input', nargs='?')
    p.add_argument('--human', action='store_true')
    p.add_argument('--groups', action='store_true')
    p.add_argument('--domains', action='store_true', help='useful for counting number of URLs by domains')
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


if __name__ == '__main__':
    main() # pragma: no cover

# TODO hmm, it's actually sort of fingerprinter... so maybe that's what I should call it

# tweet          -P-> user (not always possible to determine)
# reddit comment -P-> reddit post
# reddit post    -P-> subreddit
# YT video       -P-> user, playlist

# wikipedia footnote will have ???
# certain urls would need to treat # as parent relationship (e.g. slatestarcodex?)

# siblings are items that share a parent (could also return which one is shared)

# youtube end domain normalising: very few occurrences, so I won't care about them for now


# TODO for debugging, have special mode that only uses query param trimming one by one
# TODO show percents?

# TODO ugh. need coverage...
