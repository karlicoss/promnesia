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

    def annotate(self, text: str) -> None:
        now = datetime.now()
        self.l.append((now, text))

    def build(self):
        from srt import Subtitle, compose
        subs = (
            Subtitle(
                index=i + 1,
                start=t - self.start,
                end  =t - self.start + timedelta(seconds=1),
                content=text,
            ) for i, (t, text) in enumerate(self.l)
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
        )
        driver.get('about:blank')
        geometry = f'{W // 2}x300+0+{H - 300}'
        with hotkeys(geometry=geometry):
            rpath = path.with_suffix('.ogv')
            with record(rpath, wid=wid):
                ann = Annotator()
                yield helper, ann

            subs = path.with_suffix('.srt')
            out  = path.with_suffix('.mp4')

            check_call([
                'ffmpeg',
                '-y', # allow overwrite
                '-i', rpath,
                '-vf', f'subtitles={subs}',
                out,
            ])



# TODO need to determine that uses X automatically
@uses_x
@browsers(FF, CH)
def test_demo_show_dots(tmp_path, browser):
    # TODO wonder if it's possible to mess with settings in local storage? unlikely...

    path = Path('demos/show-dots')
    subs = path.with_suffix('.srt')

    url = 'https://slatestarcodex.com/'
    with demo_helper(tmp_path=tmp_path, browser=browser, path=path) as (helper, ann):
        driver = helper.driver

        ann.annotate('hello')
        # confirm('continue?')
        sleep(2)
        driver.get(url)

        # TODO move driver inside??
        trigger_command(driver, Command.SHOW_DOTS)

        ann.annotate('hello 2')

        sleep(3)
        # confirm('continue?')

        # TODO would be nice to actually generate subtitles??
        # TODO not sure how long to wait...
        # confirm('continue?')

        subs.write_text(ann.build())

    # TODO not sure if should keep srt file around?
    subs.unlink()




# TODO perhaps make them independent of network? Although useful for demos
