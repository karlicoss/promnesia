from contextlib import contextmanager
from datetime import timedelta, datetime
from pathlib import Path
from time import sleep
from subprocess import check_call


from common import uses_x
from end2end_test import FF, CH, browsers, _test_helper
from end2end_test import PYTHON_DOC_URL
from integration_test import index_urls
from end2end_test import confirm, trigger_command, Command
from end2end_test import configure_extension, get_window_id

from record import record, hotkeys

@uses_x
@browsers(FF, CH)
def test_demo(tmp_path, browser):
    tutorial = 'file:///usr/share/doc/python3/html/tutorial/index.html'
    urls = {
         tutorial                                                : 'TODO read this',
        'file:///usr/share/doc/python3/html/reference/index.html': None,
    }
    url = PYTHON_DOC_URL
    with _test_helper(tmp_path, index_urls(urls), url, browser=browser) as helper:
        with record():
            sleep(1)
            helper.driver.get(tutorial)
            sleep(1)
            # TODO wait??


def real_db():
    from private import real_db_path
    from tempfile import TemporaryDirectory
    import shutil
    def indexer(tdir: Path):
        tdb = tdir / 'promnesia.sqlite'
        # tdb.touch()
        shutil.copy(real_db_path, tdb)
    return indexer


class Annotator:
    def __init__(self):
        self.start = datetime.now()
        self.l = []

    def annotate(self, text: str, length=2) -> None:
        # TODO how to display during recording??
        now = datetime.now()
        print(f"ANNOTATING: {text}")
        self.l.append((now, text, length))

    def build(self):
        from srt import Subtitle, compose
        subs = (
            Subtitle(
                index=i + 1,
                start=t - self.start,
                end  =t - self.start + timedelta(seconds=length),
                content=text,
            ) for i, (t, text, length) in enumerate(self.l)
        )
        return compose(subs)



@contextmanager
def demo_helper(*, tmp_path, browser, path: Path, indexer=real_db):
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

        configure_extension(
            driver,
            host=None, port=None, # TODO meh
            notification=False,
            highlights=False,
        )
        driver.get('about:blank')
        geometry = f'{W // 2}x200+0+{H - 200}'
        with hotkeys(geometry=geometry):
            rpath = path.with_suffix('.ogv')
            with record(rpath, wid=wid):
                ann = Annotator()
                yield helper, ann

            subs = path.with_suffix('.srt')
            out  = path.with_suffix('.mp4')

            sub_settings = f"subtitles={subs}:force_style='Alignment=5,PrimaryColour=&H00ff00&'"

            check_call([
                'ffmpeg',
                '-hide_banner', '-loglevel', 'panic', # less spam
                '-y', # allow overwrite
                '-i', rpath,
                '-vf', sub_settings,
                out,
            ])


# TODO use ass?
# https://trac.ffmpeg.org/wiki/HowToBurnSubtitlesIntoVideo


demo = False


def prompt(what: str):
    if demo:
        return
    confirm(what)


def wait(x):
    print(f"Sleeping for {x} seconds")
    sleep(x)



# TODO need to determine that uses X automatically
@uses_x
@browsers(FF, CH)
def test_demo_show_dots(tmp_path, browser):
    # TODO wonder if it's possible to mess with settings in local storage? unlikely...

    path = Path('demos/show-dots')
    subs = path.with_suffix('.srt')

    # TODO fast mode??
    url = 'https://slatestarcodex.com/'
    with demo_helper(tmp_path=tmp_path, browser=browser, path=path) as (helper, ann):
        driver = helper.driver

        prompt('continue?')
        driver.get(url)

        # TODO display subs nicer??

        ann.annotate('''
On the left you can see a blogroll with recommended blogs.
Lots of sites there!
''', length=3)

        wait(3)

        ann.annotate('''
You feel like reading something new.
Which are the ones you haven't seen before?
        ''', length=3)

        # TODO rename to 'highlight visited'? or 'show visited'

        wait(3)

        # TODO request focus on 'prompt'??
        prompt('continue?')

        # TODO move driver inside??
        trigger_command(driver, Command.SHOW_DOTS)

        ann.annotate('''
The command displays dots next to the links you've already visited,
so you don't have to search browser history all over for each of them.
        ''', length=3)
        wait(3)

        ann.annotate('''
You can click straight on the ones you haven't seen before and start exploring!
        ''', length=10)

        wait(10)
        prompt('continue?')

        # TODO would be nice to actually generate subtitles??
        # TODO not sure how long to wait...

        subs.write_text(ann.build())

    # TODO not sure if should keep srt file around?
    subs.unlink()


@uses_x
@browsers(FF, CH)
def test_demo_show_dots_2(tmp_path, browser):
    path = Path('demos/show-dots-2')
    subs = path.with_suffix('.srt')

    # TODO maybe test on Baez instead?
    # TODO scroll to ?
    url = 'https://www.lesswrong.com/posts/vwqLfDfsHmiavFAGP/the-library-of-scott-alexandria#IV__Medicine__Therapy__and_Human_Enhancement'
    with demo_helper(tmp_path=tmp_path, browser=browser, path=path) as (helper, ann):
        driver = helper.driver
        driver.get(url)
        # TODO eh. maybe should start recording after the URL has loaded

        ann.annotate('''
Lots of links to explore on this page.
Which ones I haven't seen before?
''', length=5)
        wait(5)

        trigger_command(driver, Command.SHOW_DOTS)
        ann.annotate('''
Hoteky press...
        ''', length=1.5)
        wait(1.5)

        ann.annotate('''
Dots appear next to the ones I've already visited!
        ''', length=8)
        wait(8)

        # TODO contextmanager?
        subs.write_text(ann.build())

    subs.unlink()


# TODO perhaps make them independent of network? Although useful for demos

# https://twitter.com/michael_nielsen/status/1162502843921600512
@uses_x
@browsers(FF, CH)
def test_demo_child_visits(tmp_path, browser):
    path = Path('demos/child-visits')
    subs = path.with_suffix('.srt')

    # TODO display subtitles below
    with demo_helper(tmp_path=tmp_path, browser=browser, path=path) as (helper, ann):
        driver = helper.driver
        driver.get('https://twitter.com/michael_nielsen/status/1162502843921600512')

        ann.annotate('''
While browsing Twitter, I run into an account recomendation.
''', length=3)
        wait(3)

        ann.annotate('''
I value Michael Nielsen's opinion, so sure, let's check the account out.
''', length=3)
        wait(3) # TODO maybe, wait by default??

        driver.get('https://twitter.com/eriktorenberg')

        # TODO wait till loaded??

        # TODO turn contexts notification on here?
        ann.annotate('''
Notice the eye icon highlighted as green.
That means I've actually run into that account before!
        ''', length=5)
        wait(5)

        wait(1)
        trigger_command(driver, Command.ACTIVATE)
        ann.annotate('''
Let's see...
        ''', length=3)
        wait(3)

        ann.annotate('''
Apparently, I've already bookmarked something interesting from that guy before.
Surely, I should follow him!
        ''', length=8)
        wait(8)

        subs.write_text(ann.build())

    subs.unlink()
