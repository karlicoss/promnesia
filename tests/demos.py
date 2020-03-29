from contextlib import contextmanager
from datetime import timedelta, datetime
from pathlib import Path
from time import sleep
from subprocess import check_call
from typing import Optional


from common import uses_x
from end2end_test import FF, CH, browsers, _test_helper
from end2end_test import PYTHON_DOC_URL
from integration_test import index_urls
from end2end_test import confirm, trigger_command, Command
from end2end_test import configure, get_window_id

from record import record, hotkeys, CURSOR_SCRIPT, SELECT_SCRIPT


def real_db():
    from private import real_db_path, test_filter
    from tempfile import TemporaryDirectory
    import shutil
    def indexer(tdir: Path):
        tdb = tdir / 'promnesia.sqlite'
        # tdb.touch()
        shutil.copy(real_db_path, tdb)

        filt = test_filter()
        if filt is not None:
            check_call([
                'sqlite3',
                tdb,
                filt,
            ])

    return indexer


class Annotator:
    def __init__(self):
        self.start = datetime.now()
        self.l = []

    def __call__(self, *args, **kwargs) -> None:
        return self.annotate(*args, **kwargs)

    def annotate(self, text: str, length=2) -> None:
        # TODO how to display during recording??
        now = datetime.now()
        print(f"ANNOTATING: {text}")
        self.l.append((now, text, length))

    def build(self, **extra):
        from pysubs2 import SSAFile, SSAEvent, Color # type: ignore[import]
        millis = lambda td: td / timedelta(milliseconds=1)
        subs = (
            SSAEvent(
                start=millis(t - self.start),
                end  =millis(t - self.start + timedelta(seconds=length)),
                text=text.replace('\n', r'\N'), # \N necessary for SSA files
            ) for t, text, length in self.l
        )
        sf = SSAFile()
        style = sf.styles['Default'].copy()
        style.fontsize = 16 # default is 20, bit too much??
        style.outlinecolor = Color(0, 0, 0, 50) # semitransparent
        style.shadow = 0.0

        style.outline = 0.1
        style.borderstyle = 3 # no idea why 3, but it makes the background apperar in conjunction with outline

        for k, v in extra.items():
            setattr(style, k, v)
        sf.styles['Default'] = style
        for s in subs:
            sf.append(s)
        return sf.to_string('ass')



@contextmanager
def demo_helper(*, tmp_path, browser, path: Path, indexer=real_db, subs_position='topleft', size='40%', **kwargs):
    # TODO literal type??
    # https://stackoverflow.com/a/25880038/706389
    # 789
    # 456
    # 123
    spos = {
        'topleft'    : 7,
        'bottomleft' : 1,
        'bottomright': 3,
    }[subs_position]

    position = f'''
.promnesia {{
    --right: 1;
    --size:  {size};
    background-color: rgba(236, 236, 236, 0.6)
}}
    '''

    with _test_helper(tmp_path, indexer(), None, browser=browser) as helper:
        driver = helper.driver
        wid = get_window_id(driver)

        W = 2560
        H = 1440
        check_call([
            'wmctrl',
            '-i',
            '-r', wid,
            '-e', f'0,0,100,{W // 2},{H - 100}',
        ])

        extras = kwargs
        if 'highlights' not in extras:
            extras['highlights'] = False

        configure(
            driver,
            host=None, port=None, # TODO meh
            notification=False,
            position=position,
            **extras,
        )

        driver.get('about:blank')
        geometry = f'{W // 2}x400+0+{H - 400}'
        with hotkeys(geometry=geometry):
            rpath = path.with_suffix('.ogv')
            with record(rpath, wid=wid):
                ann = Annotator()
                yield helper, ann

            subs = path.with_suffix('.ssa')
            subs.write_text(ann.build(alignment=spos))
            out  = path.with_suffix('.webm')

            check_call([
                'ffmpeg',
                '-hide_banner', '-loglevel', 'panic', # less spam
                '-y', # allow overwrite
                '-i', rpath,
                '-vf', f"ass={subs}",
                out,
            ])

            # TODO unlink subs here?
            # subs.unlink()


# TODO use ass?
# https://trac.ffmpeg.org/wiki/HowToBurnSubtitlesIntoVideo


demo = False


def prompt(what: str):
    if demo:
        return
    confirm(what)


fast = False

def wait(x):
    if fast:
        return
    print(f"Sleeping for {x} seconds")
    sleep(x)


@uses_x
@browsers(FF, CH)
def test_demo_quick(tmp_path, browser):
    path = Path('demos/quick')
    with demo_helper(
            tmp_path=tmp_path,
            browser=browser,
            path=path,
            subs_position='topleft',
    ) as (helper, annotate):
        driver = helper.driver

        driver.get('https://en.wikipedia.org/wiki/Whatever_(slang)')
        annotate('''
One two three four five.
Six seven eight nine ten?
        ''', length=5)
        wait(5)


# TODO need to determine that uses X automatically
@uses_x
@browsers(FF, CH)
def test_demo_show_dots(tmp_path, browser):
    # TODO wonder if it's possible to mess with settings in local storage? unlikely...

    path = Path('demos/show-dots')

    # TODO fast mode??
    url = 'https://slatestarcodex.com/'
    with demo_helper(
            tmp_path=tmp_path,
            browser=browser,
            path=path,
            subs_position='bottomright',
    ) as (helper, annotate):
        driver = helper.driver

        driver.get(url)

        # TODO display subs nicer??

        annotate('''
On the left you can see a blogroll with recommended blogs.
Lots of sites there!
''', length=3)

        wait(3)

        annotate('''
You feel like reading something new.
Which are the ones you haven't seen before?
        ''', length=3)

        # TODO rename to 'highlight visited'? or 'show visited'

        wait(3)

        # TODO request focus on 'prompt'??
        # prompt('continue?')

        helper.show_visited()

        wait(1)

        annotate('''
The command displays dots next to the links you've already visited.
That way you don't have to search browser history all over for each of them!
        ''', length=5)
        wait(5)

        annotate('''
You can click straight on the ones you haven't seen before and start exploring!
        ''', length=10)

        wait(10)


@uses_x
@browsers(FF, CH)
def test_demo_show_dots_2(tmp_path, browser):
    path = Path('demos/show-dots-2')

    # TODO maybe test on Baez instead?
    # TODO scroll to ?
    url = 'https://www.lesswrong.com/posts/vwqLfDfsHmiavFAGP/the-library-of-scott-alexandria#IV__Medicine__Therapy__and_Human_Enhancement'
    with demo_helper(tmp_path=tmp_path, browser=browser, path=path) as (helper, annotate):
        driver = helper.driver
        driver.get(url)
        # TODO eh. maybe should start recording after the URL has loaded

        annotate('''
Lots of links to explore on this page.
Which ones I haven't seen before?
''', length=5)
        wait(5)

        trigger_command(driver, Command.SHOW_DOTS)
        annotate('''
Hoteky press...
        ''', length=1.5)
        wait(1.5)

        annotate('''
Dots appear next to the ones I've already visited!
        ''', length=8)
        wait(8)


# TODO perhaps make them independent of network? Although useful for demos

@uses_x
@browsers(FF, CH)
def test_demo_child_visits(tmp_path, browser):
    path = Path('demos/child-visits')
    with demo_helper(
            tmp_path=tmp_path,
            browser=browser,
            path=path,
            subs_position='bottomleft',
    ) as (helper, annotate):
        driver = helper.driver
        driver.get('https://twitter.com/michael_nielsen/status/1162502843921600512')

        annotate('''
While browsing Twitter, I see an account recomendation.
''', length=3)
        wait(3)

        annotate('''
I really value Michael Nielsen's opinion, so it's worth checking out.
''', length=3)
        wait(3) # TODO maybe, wait by default??

        driver.get('https://twitter.com/eriktorenberg')

        wait(1)

        # TODO wait till loaded??

        # TODO turn contexts notification on here?
        annotate('''
See the green eye icon in top right?
That means I have run into that account before!
        ''', length=5)
        wait(5)

        wait(1)
        # TODO make hotkey popup larger...
        annotate('''
Let's see...
        ''', length=2)
        wait(1)
        trigger_command(driver, Command.ACTIVATE)
        wait(1)

        annotate('''
Right, I've already bookmarked something interesting from that guy before.
Surely, I should follow him!
        ''', length=8)
        wait(8)



@uses_x
@browsers(FF, CH)
def test_demo_child_visits_2(tmp_path, browser):
    path = Path('demos/child-visits-2')
    with demo_helper(
            tmp_path=tmp_path,
            browser=browser,
            path=path,
            subs_position='bottomleft',
    ) as (helper, annotate):
        driver = helper.driver
        # TODO jeez. medium takes ages to load..
        driver.get('https://medium.com/@justlv/how-to-build-a-brain-interface-and-why-we-should-connect-our-minds-35003841c4b7')
        wait(1)

        annotate('''
I ran into this cool post on Hackernews.
Usually I'd also check out the author's blog for more content.
''', length=4)
        wait(4)

        driver.get('https://medium.com/@justlv')
        wait(1)

        annotate('''
The icon is green.
So I've interacted with the page before!
''', length=4)
        wait(4)

        wait(1)
        # TODO make hotkey popup larger...
        annotate('''
Let's see...
        ''', length=2)
        wait(1)
        helper.activate()
        wait(1)

        helper.switch_to_sidebar()

        driver.execute_script(CURSOR_SCRIPT)
        # TODO move to helper??

        tweet = driver.find_element_by_class_name('locator')
        helper.move_to(tweet)

        annotate('''
Cool, I've even tweeted about one of the posts on this blog before!
        ''', length=5)
        wait(5)

        # TODO original tweet -> smth else??
        annotate('''
Clicking on 'context' will bring me straight to the original tweet.
        ''', length=2)

        a_tweet = tweet.find_element_by_tag_name('a')
        helper.move_to(a_tweet)

        wait(2)

        a_tweet.click()

        wait(8)


from selenium import webdriver # type: ignore


def scroll_to_text(driver, text: str):
    # ActionChain doesn't work if the element isn't visible. ugh.
    # https://stackoverflow.com/questions/3401343/scroll-element-into-view-with-selenium
    # so have to resort to JS

    element = driver.find_element_by_xpath(f"//*[contains(text(), '{text}')]")

    loc = element.location
    y = loc['y']

    driver.execute_script(f'window.scrollTo(0, {y})')
    # TODO a bit of wait??
   

from end2end_test import get_webdriver


@uses_x
@browsers(FF, CH)
def test_demo_highlights(tmp_path, browser):
    assert browser == FF, browser # because of the profile_dir hack
    path = Path('demos/highlights')
    with demo_helper(
            tmp_path=tmp_path,
            browser=browser,
            path=path,
            subs_position='bottomleft',
            highlights=True,
    ) as (helper, annotate):
        # TODO is it possible to disable extension first??
        driver = helper.driver

        from private import instapaper_cookies

        # necessary to set cookies on instapaper..
        driver.get('http://instapaper.com')
        for cookie in instapaper_cookies():
            driver.add_cookie(cookie)

        driver.get('https://instapaper.com/read/1257588750')

        annotate('''
I'm using Instapaper to read and highlight articles while I'm offline on my phone.
        ''', length=5)

        scroll_to_text(driver, "where things stood")
        wait(2.5)
        scroll_to_text(driver, "As impossible as it sounds")
        wait(2.5)

        # TODO go to div class="source" -> a class="original"
        # driver without the extension
        ORIG = 'http://nautil.us/issue/66/clockwork/haunted-by-his-brother-he-revolutionized-physics-rp'
        with get_webdriver(browser, extension=False) as driver2:
            driver2.get(ORIG)

            # TODO maybe, have annotation 'start' and 'interrupt'?
            annotate('''
But if you open the original article, you can't see the annotations!
            ''', length=5)

            scroll_to_text(driver2, "where things stood")
            wait(2.5)
            scroll_to_text(driver2, "As impossible as it sounds")
            wait(2.5)

        annotate('''
Let's try it with Promnesia!
        ''', length=5)

        driver.get(ORIG)
        scroll_to_text(driver, "where things stood")
        wait(2.5)
        scroll_to_text(driver, "As impossible as it sounds")
        wait(2.5)

        annotate('''
Highlights are displayed within the original page!
        ''', length=3)
        wait(1)
        # TODO encapsulate in come object instead?..
        trigger_command(driver, Command.ACTIVATE)
        wait(2)

        annotate('''
It works with any highlight source, whether it's Pocket, Hypothes.is or anything else.
        ''', length=4)
        wait(4)

        annotate('''
Let me demonstrate...
        ''')
        wait(2)

        driver.get('https://en.wikipedia.org/wiki/Empty_Spaces')
        wait(3)
        trigger_command(driver, Command.ACTIVATE)

        # TODO move cursor to the note?
        annotate('''
This clipping is in my plaintext notes!
It's not using any annotation service -- it's just an org-mode file!
        ''', length=5)
        wait(7)


# TODO https://www.youtube.com/watch?v=YKLpz025vYY
# TODO https://www.youtube.com/watch?v=17Q0tJZcsnY
# TODO https://en.wikipedia.org/wiki/SnapPea

@uses_x
@browsers(FF, CH)
def test_demo_how_did_i_get_here(tmp_path, browser):
    path = Path('demos/how_did_i_get_here')
    with demo_helper(
            tmp_path=tmp_path,
            browser=browser,
            path=path,
            subs_position='bottomleft',
    ) as (helper, annotate):
        driver = helper.driver
        driver.get('https://www.amazon.co.uk/Topoi-Categorial-Analysis-Logic-Mathematics/dp/0486450260')

        annotate('''
I found this link in my bookmarks.
Hmmm, can't remember, why I added it.
        ''', length=4)
        wait(4)

        helper.activate()
        wait(1)

        annotate('''
If you click on a timestamp, you'll jump straight into the place in timeline where the visit occured.
        ''', length=6)
        wait(2)

        helper.switch_to_sidebar()

        driver.execute_script(CURSOR_SCRIPT)
        last_dt = list(driver.find_elements_by_class_name('datetime'))[-1]
        helper.move_to(last_dt)
        wait(4)

        # TODO helper to click 'the' link on the element??
        # last_dt.find_element_by_tag_name('a').click()
        # TODO highlight clicks??
        last_dt.click()
        driver.switch_to.window(driver.window_handles[-1])
        driver.execute_script(CURSOR_SCRIPT)
        wait(1)

        annotate('''
Looks like right before clicking on the Amazon link, I was reading
a book on math.ucr.edu/home/baez/planck
Let's see...
        ''', length=7)
        wait(3)
        #
        #
        # meh..

        node8 = 'math.ucr.edu/home/baez/planck/node8.html'
        baez = driver.find_element_by_link_text(node8)
        helper.move_to(baez)
        wait(4)

        # driver.execute_script(f"window.open('{node8}')")
        # TODO encapsulate??
        baez.click()
        # driver.switch_to.window(driver.window_handles[-1])

        annotate('''
And here's the reference to the book!
        ''', length=4)
        driver.execute_script(
            # meh
            SELECT_SCRIPT + "\n" + "selectText(document.getElementsByTagName('dd')[17])"
        )
        wait(6)
    # TODO mention that it's chrome history! so I wouldn't have it in my browser history in firefox



@uses_x
@browsers(FF, CH)
def test_demo_watch_later(tmp_path, browser):
    path = Path('demos/watch_later')
    with demo_helper(
            tmp_path=tmp_path,
            browser=browser,
            path=path,
            subs_position='bottomleft',
    ) as (helper, annotate):
        driver = helper.driver

        driver.get('https://www.youtube.com/watch?v=DvT-O_DI4t4')

        annotate('''
I have this video in my "Watch later" playlist.
I wonder why?
        ''', length=4)

        helper.activate()
        wait(1)

        annotate('''
Aha, my friend sent it to me on Telegram.
The sidebar also conveniently displays the message that mentions it.
        ''', length=5)
        wait(5)

        annotate('''
Once I watched it, I want to discuss it with the friend.
        ''', length=3)
        wait(3)

        helper.switch_to_sidebar()
        driver.execute_script(CURSOR_SCRIPT)
        loc = driver.find_element_by_class_name('locator')
        helper.move_to(loc)

        annotate('''
Clicking on the "chat with" link will jump straight into that message, in Telegram web app.
        ''', length=5)
        wait(2)
        a_loc = loc.find_element_by_tag_name('a')
        helper.move_to(a_loc)
        wait(3)

        # TODO not actually clicking, becaus I have no idea how to censor Telegram into a proper demo
        # document.getElementsByClassName('im_dialogs_col')[0].style.display = 'none'
        # TODO get url

        # TODO how to censor the link???

        # driver.get('https://web.telegram.org')
        # breakpoint()
        #
        # TODO hide im_message_from_photo
        # .im_message_body {
        #     color:
        #     white;
        # }
        # TODO <span class="peer_initials nocopy im_message_from_photo user_bgcolor_4" data-content="initials_here"></span>
