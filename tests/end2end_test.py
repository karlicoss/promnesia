#!/usr/bin/env python3
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep

import pytest
from selenium import webdriver

from common import skip_if_ci
from server_test import _test_helper as server
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


@skip_if_ci("uses X server ")
def test_visits(tmp_path):
    tdir = Path(tmp_path)
    # TODO reuse same index as in hypothesis
    # TODO rerun server

    with server(tdir) as srv, get_webdriver() as driver:
        port = srv.port
        configure_extension(driver, port=port)
        sleep(0.5)

        driver.get('https://takeout.google.com/settings/takeout')
        sleep(1)

        trigger_hotkey()

        # TODO log what one is exptected to see?



if __name__ == '__main__':
    pytest.main(['-s', __file__])
