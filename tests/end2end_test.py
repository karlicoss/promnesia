#!/usr/bin/env python3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory
from subprocess import check_call
from time import sleep
from typing import NamedTuple

import pytest # type: ignore

from selenium import webdriver # type: ignore
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By


from kython.tui import getch_or_fail

from common import skip_if_ci, uses_x
from integration_test import index_hypothesis, index_local_chrome
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


def _get_webdriver(tdir: Path, browser: str, headless: bool):
    addon = get_addon_path(browser=browser)
    if browser == B.FF:
        profile = webdriver.FirefoxProfile(str(tdir))
        options = webdriver.FirefoxOptions()
        options.headless = headless
        # use firefox from here to test https://www.mozilla.org/en-GB/firefox/developer/
        driver = webdriver.Firefox(profile, options=options)

        # driver = webdriver.Firefox(profile, firefox_binary='/L/soft/firefox-dev/firefox/firefox', options=options)
        # TODO how to pass it here properly?

        driver.install_addon(str(addon), temporary=True)
    elif browser == B.CH:
        # TODO ugh. very hacky...
        ex = tdir / 'extension.zip'
        files = [x.name for x in addon.iterdir()]
        check_call(['apack', '-q', str(ex), *files], cwd=addon)
        # looks like chrome uses temporary dir for data anyway
        options = webdriver.ChromeOptions()
        options.headless = headless
        options.add_extension(ex)
        driver = webdriver.Chrome(options=options)
    else:
        raise RuntimeError(f'Unexpected browser {browser}')
    return driver


# TODO copy paste from grasp
@contextmanager
def get_webdriver(browser: str, headless: bool):
    with TemporaryDirectory() as td:
        tdir = Path(td)
        driver = _get_webdriver(tdir, browser=browser, headless=headless)
        try:
            yield driver
        finally:
            driver.close()


def set_host(*, driver, host: str, port: str):
    ep = driver.find_element_by_id('host_id') # TODO rename to 'backend'?
    ep.clear()
    ep.send_keys(f'{host}:{port}')


def configure_extension(driver, *, host: str='http://localhost', port: str, show_dots: bool=True, blacklist=()):
    # TODO log properly
    print(f"Setting: port {port}, show_dots {show_dots}")

    open_extension_page(driver, page='options_page.html')
    sleep(1) # err, wtf? otherwise not always interacts with the elements correctly

    set_host(driver=driver, host=host, port=port)

    dots = driver.find_element_by_id('dots_id')
    if dots.is_selected() != show_dots:
        dots.click()
    assert dots.is_selected() == show_dots

    bl = driver.find_element_by_id('blacklist_id')
    bl.send_keys('\n'.join(blacklist))

    se = driver.find_element_by_id('save_id')
    se.click()

    driver.switch_to.alert.accept()


def trigger_hotkey(hotkey):
    print("sending hotkey!")
    import pyautogui # type: ignore
    pyautogui.hotkey(*hotkey)


class TestHelper(NamedTuple):
    driver: webdriver.Remote

    def open_page(self, page: str) -> None:
        open_extension_page(self.driver, page)


def confirm(what: str):
    import click # type: ignore
    click.confirm(what, abort=True)


@contextmanager
def _test_helper(tmp_path, indexer, test_url: str, show_dots: bool=False, browser: str=B.FF, headless: bool=False):
    tdir = Path(tmp_path)

    indexer(tdir)
    config = tdir / 'test_config.py'
    with wserver(config=config) as srv, get_webdriver(browser=browser, headless=headless) as driver:
        port = srv.port
        configure_extension(driver, port=port, show_dots=show_dots)
        sleep(0.5)

        driver.get(test_url)
        sleep(3)

        yield TestHelper(driver=driver)


class Hotkey:
    ACTIVATE = ('ctrl', 'alt', 'w')
    DOTS     = ('ctrl', 'alt', 'v')
    SEARCH   = ('ctrl', 'alt', 'b')



@pytest.mark.parametrize("browser", [B.CH, B.FF])
def test_installs(tmp_path, browser):
    with get_webdriver(browser=browser, headless=True):
        # just shouldn't crash
        pass


# TODO detect if uses X from get_webdriver fixture?
@pytest.mark.parametrize("browser", [B.FF]) # TODO chrome too
def test_settings(tmp_path, browser):
    with get_webdriver(browser=browser, headless=True) as driver:
        configure_extension(driver, port='12345', show_dots=False)
        # just shouldn't crash
        driver.get('about:blank')
        open_extension_page(driver, page='options_page.html')
        hh = driver.find_element_by_id('host_id')
        assert hh.get_attribute('value') == 'http://localhost:12345'


@pytest.mark.parametrize("browser", [B.FF]) # TODO chrome too
def test_backend_status(tmp_path, browser):
    with get_webdriver(browser=browser, headless=True) as driver:
        open_extension_page(driver, page='options_page.html')
        sleep(1) # ugh. for some reason pause here seems necessary..
        set_host(driver=driver, host='https://nosuchhost.com', port='1234')
        driver.find_element_by_id('backend_status_id').click()
        sleep(1 + 0.5) # needs enough time for timeout to trigger...

        alert = driver.switch_to.alert
        assert 'ERROR' in alert.text
        driver.switch_to.alert.accept()

        sleep(0.5)

        # ugh. extra alert...
        driver.switch_to.alert.accept()

        # TODO implement positive check??


@uses_x
@pytest.mark.parametrize("browser", [B.FF]) # TODO chrome too
def test_blacklist_custom(tmp_path, browser):
    with get_webdriver(browser=browser, headless=False) as driver:
        configure_extension(driver, port='12345', blacklist=('stackoverflow.com',))
        driver.get('http://stackoverflow.com')
        confirm('page should be blacklisted (black icon)')


@uses_x
@pytest.mark.parametrize("browser", [B.FF]) # TODO chrome too
def test_blacklist_builtin(tmp_path, browser):
    with get_webdriver(browser=browser, headless=False) as driver:
        configure_extension(driver, port='12345')
        driver.get('https://www.hsbc.co.uk/mortgages/')
        confirm('page should be blacklisted (black icon)')


@uses_x
@pytest.mark.parametrize("browser", [B.FF, B.CH])
def test_add_to_blacklist(tmp_path, browser):
    with get_webdriver(browser=browser, headless=False) as driver:
        configure_extension(driver, port='12345')
        driver.get('https://example.com')
        chain = webdriver.ActionChains(driver)
        chain.move_to_element(driver.find_element_by_tag_name('h1')).context_click().perform()

        # looks like selenium can't interact with browser context menu...
        import pyautogui # type: ignore

        if driver.name == 'chrome':
            offset = 2 # Inspect, View page source
        else:
            offset = 0
        pyautogui.typewrite(['up'] + ['up'] * offset + ['enter'], interval=0.5)

        driver.get(driver.current_url)
        confirm('page should be blacklisted (black icon)')


@uses_x
def test_visits(tmp_path):
    test_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    # test_url = "file:///usr/share/doc/python3/html/library/contextlib.html" # TODO ??
    with _test_helper(tmp_path, index_hypothesis, test_url):
        trigger_hotkey(hotkey=Hotkey.ACTIVATE)
        confirm('you should see hypothesis contexts')


@uses_x
def test_around(tmp_path):
    test_url = "about:blank"
    with _test_helper(tmp_path, index_hypothesis, test_url) as h:
        ts = int(datetime.strptime("2017-05-22T10:59:00.082375+00:00", '%Y-%m-%dT%H:%M:%S.%f%z').timestamp())
        h.open_page(f'search.html?timestamp={ts}')
        confirm('you should see search results, "anthrocidal" should be highlighted red')


# TODO skip if not my hostname
@uses_x
def test_chrome_visits(tmp_path):
    test_url = "https://en.wikipedia.org/wiki/Amplituhedron"
    test_url = "https://en.wikipedia.org/wiki/Symplectic_vector_space"
    with _test_helper(tmp_path, index_local_chrome, test_url):
        trigger_hotkey(hotkey=Hotkey.ACTIVATE)
        confirm("You shoud see chrome visits now; with time spent")


@uses_x
def test_show_dots(tmp_path):
    test_url = "https://en.wikipedia.org/wiki/Symplectic_group"
    with _test_helper(tmp_path, index_local_chrome, test_url, show_dots=True):
        trigger_hotkey(hotkey=Hotkey.DOTS)
        confirm("You should see dots now near SL group, U group, Representation theory")


@uses_x
def test_search(tmp_path):
    test_url = "https://en.wikipedia.org/wiki/Symplectic_vector_space"
    with _test_helper(tmp_path, index_local_chrome, test_url):
        trigger_hotkey(hotkey=Hotkey.SEARCH)
        confirm("You shoud see chrome visits now; with time spent")


@uses_x
def test_new_background_tab(tmp_path):
    start_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    # bg_url_text = "El Proceso (The Process)"
    # TODO generate some fake data instead?
    with _test_helper(tmp_path, index_hypothesis, start_url) as helper:
        confirm('you should see notification about contexts')
        helper.driver.find_element(By.XPATH, '//div[@class="logo"]/a').send_keys(Keys.CONTROL + Keys.ENTER)
        confirm('you should not see any new notifications')
        # TODO switch to new tab?
        # TODO https://www.e-flux.com/journal/53/


@uses_x
@pytest.mark.parametrize("browser", [B.FF, B.CH])
def test_local_page(tmp_path, browser):
    url = "file:///usr/share/doc/python3/html/index.html"
    with _test_helper(tmp_path, index_hypothesis, url, browser=browser) as helper:
        confirm('Icon should not be black (TODO more comprehensive test maybe?)')

if __name__ == '__main__':
    # TODO ugh need to figure out PATH
    # python3 -m pytest -s tests/server_test.py::test_query 
    pytest.main(['-s', __file__])


# TODO perhaps make them independent of network? Although useful for demos
