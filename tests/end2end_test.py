#!/usr/bin/env python3
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from subprocess import check_call
from time import sleep

import pytest
from selenium import webdriver


from kython.tui import getch_or_fail

from common import skip_if_ci
from integration_test import index_instapaper, index_local_chrome
from server_test import wserver
from firefox_helper import open_extension_page


class Browser:
    FF = 'firefox'
    CH = 'chrome'
B = Browser

def get_addon_path(browser: str) -> Path:
    # TODO compile first?
    addon_path = (Path(__file__).parent.parent / 'extension' / 'dist' / browser).absolute()
    # TODO assert manifest or smth?
    assert addon_path.exists()
    assert (addon_path / 'manifest.json').exists()
    return addon_path


# TODO copy paste from grasp
@contextmanager
def get_webdriver(browser: str=B.FF):
    addon = get_addon_path(browser=browser)
    with TemporaryDirectory() as td:
        tdir = Path(td)
        if browser == B.FF:
            profile = webdriver.FirefoxProfile(str(tdir))
            # use firefox from here to test https://www.mozilla.org/en-GB/firefox/developer/
            driver = webdriver.Firefox(profile, firefox_binary='/L/soft/firefox-dev/firefox/firefox')
            # TODO this should be under with...
            driver.install_addon(str(addon), temporary=True)
        elif browser == B.CH:
            # TODO ugh. very hacky...
            ex = tdir / 'extension.zip'
            files = [x.name for x in addon.iterdir()]
            check_call(['apack', '-q', str(ex), *files], cwd=addon)
            # looks like chrome uses temporary dir for data anyway
            options = webdriver.ChromeOptions()
            options.add_extension(ex)
            driver = webdriver.Chrome(options=options)
        else:
            raise RuntimeError(f'Unexpected browser {browser}')
        try:
            yield driver
        finally:
            driver.close()


def configure_extension(driver, port: str, show_dots: bool):
    open_extension_page(driver, page='options_page.html')

    ep = driver.find_element_by_id('host_id') # TODO rename to 'endpoint'?
    ep.clear()
    ep.send_keys(f'http://localhost:{port}')

    dots = driver.find_element_by_id('dots_id')
    if dots.is_selected() != show_dots:
        dots.click()
    assert dots.is_selected() == show_dots

    se = driver.find_element_by_id('save_id')
    se.click()

    driver.switch_to.alert.accept()


def trigger_hotkey(hotkey):
    print("sending hotkey!")
    import pyautogui # type: ignore
    pyautogui.hotkey(*hotkey)


@contextmanager
def _test_helper(tmp_path, indexer, test_url: str, show_dots: bool=False):
    tdir = Path(tmp_path)

    indexer(tdir)
    config = tdir / 'test_config.py'
    with wserver(config=config) as srv, get_webdriver() as driver:
        port = srv.port
        configure_extension(driver, port=port, show_dots=show_dots)
        sleep(0.5)

        driver.get(test_url)
        sleep(3)

        yield

        # TODO log what one is expected to see?
        print("Press any key to finish")
        getch_or_fail()


class Hotkey:
    ACTIVATE = ('ctrl', 'alt', 'w')
    DOTS     = ('ctrl', 'alt', 'v')


# TODO could be headless?
@skip_if_ci("uses X")
@pytest.mark.parametrize("browser", [B.CH, B.FF])
def test_installs(tmp_path, browser):
    with get_webdriver(browser=browser):
        # just shouldn't crash
        pass


@skip_if_ci("uses X server ")
def test_visits(tmp_path):
    test_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    with _test_helper(tmp_path, index_instapaper, test_url):
        trigger_hotkey(hotkey=Hotkey.ACTIVATE)
        print("You shoud see hypothesis contexts now")


# TODO skip if not my hostname
@skip_if_ci("uses X server")
def test_chrome_visits(tmp_path):
    test_url = "https://en.wikipedia.org/wiki/Amplituhedron"
    test_url = "https://en.wikipedia.org/wiki/Symplectic_vector_space"
    with _test_helper(tmp_path, index_local_chrome, test_url):
        trigger_hotkey(hotkey=Hotkey.ACTIVATE)
        print("You shoud see chrome visits now; with time spent")


@skip_if_ci("uses X server")
def test_show_dots(tmp_path):
    test_url = "https://en.wikipedia.org/wiki/Symplectic_group"
    with _test_helper(tmp_path, index_local_chrome, test_url):
        trigger_hotkey(hotkey=Hotkey.DOTS)
        print("You should see dots now near SL group, U group, Representation theory")


if __name__ == '__main__':
    # TODO ugh need to figure out PATH
    # python3 -m pytest -s tests/server_test.py::test_query 
    pytest.main(['-s', __file__])

# TODO perhaps make them independent of network? Although useful for demos
