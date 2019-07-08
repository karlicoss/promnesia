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


def get_addon_path() -> Path:
    addon_path = (Path(__file__).parent.parent / 'extension' / 'dist' / 'firefox').absolute()
    # TODO assert manifest or smth?
    assert addon_path.exists()
    assert (addon_path / 'manifest.json').exists()
    return addon_path


# TODO copy paste from grasp
@contextmanager
def get_webdriver():
    addon = get_addon_path()
    with TemporaryDirectory() as td:
        profile = webdriver.FirefoxProfile(td)
        # use firefox from here to test https://www.mozilla.org/en-GB/firefox/developer/
        driver = webdriver.Firefox(profile, firefox_binary='/L/soft/firefox-dev/firefox/firefox')
        try:
            driver.install_addon(str(addon), temporary=True)
            yield driver
        finally:
            driver.close()


def configure_extension(driver, port: str):
    open_extension_page(driver, page='options_page.html')

    ep = driver.find_element_by_id('host_id') # TODO rename to 'endpoint'?
    ep.clear()
    ep.send_keys(f'http://localhost:{port}')

    dots = driver.find_element_by_id('dots_id')
    if dots.is_selected():
        dots.click()
        assert not dots.is_selected()

    se = driver.find_element_by_id('save_id')
    se.click()

    driver.switch_to.alert.accept()


def trigger_hotkey():
    print("sending hotkey!")
    import pyautogui # type: ignore
    pyautogui.hotkey('ctrl', 'alt', 'w')


def _test_helper(tmp_path, indexer, test_url: str):
    tdir = Path(tmp_path)

    indexer(tdir)
    config = tdir / 'test_config.py'
    with wserver(config=config) as srv, get_webdriver() as driver:
        port = srv.port
        configure_extension(driver, port=port)
        sleep(0.5)

        driver.get(test_url)
        sleep(3)

        trigger_hotkey()

        # TODO log what one is expected to see?
        print("Press any key to finish")
        getch_or_fail()


@skip_if_ci("uses X server ")
def test_visits(tmp_path):
    test_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    _test_helper(tmp_path, index_instapaper, test_url)


# TODO skip if not my hostname
@skip_if_ci("uses X server")
def test_chrome_visits(tmp_path):
    test_url = "https://en.wikipedia.org/wiki/Amplituhedron"
    _test_helper(tmp_path, index_local_chrome, test_url)


if __name__ == '__main__':
    # TODO ugh need to figure out PATH
    # python3 -m pytest -s tests/server_test.py::test_query 
    pytest.main(['-s', __file__])
