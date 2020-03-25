from contextlib import contextmanager
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


@contextmanager
def demo_helper(*, tmp_path, browser, name: str, indexer=real_db):
    with _test_helper(tmp_path, indexer(), None, browser=browser) as helper:
        driver = helper.driver
        wid = get_window_id(driver)

        W = 2560
        H = 1440
        check_call([
            'wmctrl',
            '-i',
            '-r', wid,
            '-e', f'0,0,0,{W // 2},{H}',
        ])

        configure_extension(
            driver,
            host=None, port=None, # TODO meh
            notification=False,
        )
        driver.get('about:blank')
        # TODO resize window??
        with hotkeys():
            with record(name, wid=wid):
                yield helper


# TODO need to determine that uses X automatically
@uses_x
@browsers(FF, CH)
def test_demo_show_dots(tmp_path, browser):
    # TODO wonder if it's possible to mess with settings in local storage? unlikely...
    url = 'https://slatestarcodex.com/'
    with demo_helper(tmp_path=tmp_path, browser=browser, name='demos/show-dots.ogv') as helper:
        driver = helper.driver

        confirm('continue?')
        driver.get(url)

        # TODO move driver inside??
        trigger_command(driver, Command.SHOW_DOTS)

        confirm('continue?')

        # TODO would be nice to actually generate subtitles??
        # TODO not sure how long to wait...
        confirm('continue?')


# TODO perhaps make them independent of network? Although useful for demos
