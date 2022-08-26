from typing import cast

import pytest # type: ignore

from promnesia.cannon import canonify, CanonifyException

# TODO should actually understand 'sequences'?
# e.g.
# https://www.scottaaronson.com/blog/?p=3167#comment-1731882 is kinda hierarchy of scottaaronson.com, post 3167 and comment 1731882
# but when working with it from server, would be easier to just do multiple queries I guess..
# https://www.scottaaronson.com/blog/?p=3167 is kind ahierarchy of scottaaronson.com ;


param = pytest.mark.parametrize


# mark stuff that in interesting as a testcase, but I'm not sure about yet
TODO = cast(str, object())


def check(url, expected):
    if expected is TODO:
        pytest.skip(f"'{url}' will be handled later")
    assert canonify(url) == expected


# TODO assume spaces are not meaninfgul??
# then could align URLs etc?

@param('url,expected', [(
    'https://www.youtube.com/watch?t=491s&v=1NHbPN9pNPM&index=63&list=WL',
    # NOTE: t= reordered, makes it more hierarchical
    # list as well, I guess makes the most sense to keep it at the very end.. since lists are more like tags
    'youtube.com/watch?v=1NHbPN9pNPM&t=491s&list=WL'
), (
    'youtube.com/watch?v=wHrCkyoe72U&feature=share&time_continue=6',
    'youtube.com/watch?v=wHrCkyoe72U'
), (
    'youtube.com/embed/nyc6RJEEe0U?feature=oembed',
    'youtube.com/watch?v=nyc6RJEEe0U'
), (
    'https://youtu.be/iCvmsMzlF7o?list=WL',
    'youtube.com/watch?v=iCvmsMzlF7o&list=WL'
),
    # TODO can even be like that or contain timestamp (&t=)
    # TODO warn if param already present? shouldn't happen..

    # TODO could be interesting to do automatic rule extraction by querying one represnetative and then extracting canonical

    # TODO national domains don't matter for youtube

    # [*, 'youtube', ANY_DOMAIN] / 'embed' -> 'youtube.com/watch'
    # TODO use regex backrefs?
    #
(
    'm.youtube.com/watch?v=Zn6gV2sdl38',
    'youtube.com/watch?v=Zn6gV2sdl38'
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


@param('url,expected', [(
    'https://web.archive.org/web/20090902224414/http://reason.com/news/show/119237.html',
    'reason.com/news/show/119237.html',
)])
def test_archiveorg(url, expected):
    assert canonify(url) == expected


# ugh. good example of motication for cannon.py?
@param('url,expected', [(
    'https://news.ycombinator.com/from?site=jacopo.io',
    'jacopo.io',
), (
    'https://news.ycombinator.com/item?id=25099862',
    'news.ycombinator.com/item?id=25099862',
), (
    'https://news.ycombinator.com/reply?id=25100035&goto=item%3Fid%3D25099862%2325100035',
    TODO,
)])
def test_hackernews(url, expected):
    check(url, expected)


@param('url, expected', [
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

# ugh. good example of motication for cannon.py?
@param('url,expected', [
    ( 'https://app.getpocket.com/read/3479402594'
    , 'app.getpocket.com/read/3479402594'
    ),

    ( 'https://getpocket.com/read/3479402594'
    , 'app.getpocket.com/read/3479402594'
    ),
])
def test_pocket(url, expected):
    assert canonify(url) == expected

@pytest.mark.parametrize("url,expected", [
    # TODO ?? 'https://groups.google.com/a/list.hypothes.is/forum/#!topic/dev/kcmS7H8ssis',
    #
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
    , 'youtube.com/watch?v=hvoQiF0kBI8&list=WL',
    ),
    ( 'https://www.youtube.com/watch?list=WL&v=hvoQiF0kBI8&index=2'
    , 'youtube.com/watch?v=hvoQiF0kBI8&list=WL',
    ),

    # TODO def need to allow the _user_ to define the rules.
    # no way I can predict everything
    # basically, allow *interactively* select
    # also allow introspection, which rule matched?
    ( 'https://bbs.archlinux.org/viewtopic.php?id=212740'
    , 'bbs.archlinux.org/viewtopic.php?id=212740',
    ),

    ( 'https://ubuntuforums.org/showthread.php?t=1403470&s=0dd67bdb12559c22e73a220752db50c7&p=8806195#post8806195'
    , 'ubuntuforums.org/showthread.php?t=1403470&p=8806195',
    ),

    ( 'https://arstechnica.com/?p=1371299',
      'arstechnica.com/?p=1371299',
      # eh. it's a redirect to https://arstechnica.com/information-technology/2018/09/dozens-of-ios-apps-surreptitiously-share-user-location-data-with-tracking-firms/
      # however in the page body there is <link rel="shorturl" href="https://arstechnica.com/?p=1371299"> ...
    ),

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

@pytest.mark.parametrize("url,expected", [
    ('https://news.ycombinator.com/item?id=', 'news.ycombinator.com/item?id='),
    ('https://www.youtube.com/watch?v=hvoQiF0kBI8&list&index=2',
     'youtube.com/watch?v=hvoQiF0kBI8&list='),
])
def test_empty_query_parameter(url, expected):
    assert canonify(url) == expected

@pytest.mark.parametrize("url,expected", [
    ('http://www.isfdb.org/cgi-bin/title.cgi?2172', 'isfdb.org/cgi-bin/title.cgi?2172='),
    ('http://www.isfdb.org/cgi-bin/title.cgi?2172+1', 'isfdb.org/cgi-bin/title.cgi?2172%201='),
    ('http://www.isfdb.org/cgi-bin/title.cgi?2172&foo=bar&baz&quux', 'isfdb.org/cgi-bin/title.cgi?2172=&baz=&foo=bar&quux='),
])
def test_qkeep_true(url, expected):
    assert canonify(url) == expected
