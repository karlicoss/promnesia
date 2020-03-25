from contextlib import contextmanager
from pathlib import Path
from time import sleep


from common import uses_x
from end2end_test import FF, CH, browsers, _test_helper
from end2end_test import PYTHON_DOC_URL
from integration_test import index_urls
from end2end_test import confirm
from end2end_test import configure_extension

from record import record

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
        shutil.copy(real_db_path, tdb)
    return indexer


# TODO need to determine that uses X automatically
@uses_x
@browsers(FF, CH)
def test_demo_show_dots(tmp_path, browser):
    # TODO wonder if it's possible to mess with settings in local storage? unlikely...
    url = 'https://slatestarcodex.com/'
    with _test_helper(tmp_path, real_db(), None, browser=browser) as helper, record('demos/show-dots.ogv'):
        # TODO make a method of helper??
        configure_extension(
            helper.driver,
            host=None, port=None, # TODO meh
            notification=False,
        )
        # TODO do it before recording??
        helper.driver.get('about:blank')

        confirm('continue?')
        helper.driver.get(url)
        # TODO would be nice to actually generate subtitles??
        # TODO not sure how long to wait...
        confirm('continue?')


# TODO perhaps make them independent of network? Although useful for demos
