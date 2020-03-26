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
                '-y', # allow overwrite
                '-i', rpath,
                '-vf', sub_settings,
                out,
            ])


# TODO use ass?
# https://trac.ffmpeg.org/wiki/HowToBurnSubtitlesIntoVideo


# TODO need to determine that uses X automatically
@uses_x
@browsers(FF, CH)
def test_demo_show_dots(tmp_path, browser):
    # TODO wonder if it's possible to mess with settings in local storage? unlikely...

    path = Path('demos/show-dots')
    subs = path.with_suffix('.srt')

    # TODO fast mode??

    demo = True

    def prompt(what: str):
        if demo:
            return
        confirm(what)


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

        sleep(3)

        ann.annotate('''
You feel like reading something new.
Which are the ones you haven't seen before?
        ''', length=3)

        # TODO rename to 'highlight visited'? or 'show visited'

        sleep(3)

        # TODO request focus on 'prompt'??
        prompt('continue?')

        # TODO move driver inside??
        trigger_command(driver, Command.SHOW_DOTS)

        ann.annotate('''
The command displays dots next to the links you've already visited,
so you don't have to search browser history all over for each of them.
        ''', length=3)
        sleep(3)

        ann.annotate('''
You can click straight on the ones you haven't seen before and start exploring!
        ''', length=4)

        sleep(4)
        prompt('continue?')

        # TODO would be nice to actually generate subtitles??
        # TODO not sure how long to wait...

        subs.write_text(ann.build())

    # TODO not sure if should keep srt file around?
    subs.unlink()




# TODO perhaps make them independent of network? Although useful for demos
