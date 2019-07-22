#!/usr/bin/env python3
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from subprocess import check_call
from time import sleep

import pytest # type: ignore
from selenium import webdriver # type: ignore


from kython.tui import getch_or_fail

from common import skip_if_ci
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
        driver = webdriver.Firefox(profile, firefox_binary='/L/soft/firefox-dev/firefox/firefox', options=options)
        # TODO this should be under with...
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
def get_webdriver(browser: str=B.FF, headless=False):
    with TemporaryDirectory() as td:
        tdir = Path(td)
        driver = _get_webdriver(tdir, browser=browser, headless=headless)
        try:
            yield driver
        finally:
            driver.close()


def configure_extension(driver, port: str, show_dots: bool=True, blacklist=()):
    # TODO log properly
    print(f"Setting: port {port}, show_dots {show_dots}")

    open_extension_page(driver, page='options_page.html')
    sleep(1) # err, wtf? otherwise not always interacts with the elements correctly

    ep = driver.find_element_by_id('host_id') # TODO rename to 'endpoint'?
    ep.clear()
    ep.send_keys(f'http://localhost:{port}')

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
    SEARCH   = ('ctrl', 'alt', 'b')
 

# TODO run this test on CI??
@skip_if_ci("uses X")
@pytest.mark.parametrize("browser", [B.CH, B.FF])
def test_installs(tmp_path, browser):
    with get_webdriver(browser=browser, headless=True):
        # just shouldn't crash
        pass


@skip_if_ci("uses X")
@pytest.mark.parametrize("browser", [B.FF]) # TODO chrome too
def test_settings(tmp_path, browser):
    with get_webdriver(browser=browser, headless=True) as driver:
        configure_extension(driver, port='12345', show_dots=False)
        # just shouldn't crash
        driver.get('about:blank')
        open_extension_page(driver, page='options_page.html')
        hh = driver.find_element_by_id('host_id')
        assert hh.get_attribute('value') == 'http://localhost:12345'


@skip_if_ci("uses X")
@pytest.mark.parametrize("browser", [B.FF]) # TODO chrome too
def test_blacklist_user(tmp_path, browser):
    with get_webdriver(browser=browser, headless=False) as driver:
        configure_extension(driver, port='12345', blacklist=('stackoverflow.com',))
        driver.get('http://stackoverflow.com')
        print("Should be blacklisted!")


@skip_if_ci("uses X")
@pytest.mark.parametrize("browser", [B.FF]) # TODO chrome too
def test_blacklist_builtin(tmp_path, browser):
    with get_webdriver(browser=browser, headless=False) as driver:
        configure_extension(driver, port='12345')
        driver.get('https://www.hsbc.co.uk/mortgages/')
        print("Should be blacklisted!")


@skip_if_ci("uses X")
@pytest.mark.parametrize("browser", [B.FF]) # TODO chrome too
def test_add_to_blacklist(tmp_path, browser):
    with get_webdriver(browser=browser, headless=False) as driver:
        configure_extension(driver, port='12345')
        driver.get('https://example.com')
        chain = webdriver.ActionChains(driver)
        chain.move_to_element(driver.find_element_by_tag_name('h1')).context_click().perform()

        # looks like selenium can't interact with browser context menu...
        import pyautogui # type: ignore
        # assumes extension context menu item is last
        pyautogui.typewrite(['up', 'enter'], interval=0.5)

        driver.get(driver.current_url)
        print("Should be blacklisted now!")



@skip_if_ci("uses X server ")
def test_visits(tmp_path):
    test_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    # test_url = "file:///usr/share/doc/python3/html/library/contextlib.html" # TODO ??
    with _test_helper(tmp_path, index_hypothesis, test_url):
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
    with _test_helper(tmp_path, index_local_chrome, test_url, show_dots=True):
        trigger_hotkey(hotkey=Hotkey.DOTS)
        print("You should see dots now near SL group, U group, Representation theory")


@skip_if_ci("uses X server")
def test_search(tmp_path):
    test_url = "https://en.wikipedia.org/wiki/Symplectic_vector_space"
    with _test_helper(tmp_path, index_local_chrome, test_url):
        trigger_hotkey(hotkey=Hotkey.SEARCH)
        print("You shoud see chrome visits now; with time spent")
        pass

if __name__ == '__main__':
    # TODO ugh need to figure out PATH
    # python3 -m pytest -s tests/server_test.py::test_query 
    pytest.main(['-s', __file__])

# TODO perhaps make them independent of network? Although useful for demos
