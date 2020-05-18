#!/usr/bin/env python3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory
from subprocess import check_call, check_output
from time import sleep
from typing import NamedTuple, Optional

import pytest # type: ignore

if __name__ == '__main__':
    # TODO ugh need to figure out PATH
    # python3 -m pytest -s tests/server_test.py::test_query
    pytest.main(['-s', __file__])


from selenium import webdriver # type: ignore
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By


from common import under_ci, skip_if_ci, uses_x
from integration_test import index_hypothesis, index_local_chrome, index_urls
from server_test import wserver
from firefox_helper import open_extension_page


class Browser(NamedTuple):
    dist: str
    headless: bool

    @property
    def name(self) -> str:
        return self.dist.split('-')[0] # TODO meh

    def skip_ci_x(self):
        if under_ci() and not self.headless:
            pytest.skip("Only can't use headless browser on CI")


FF  = Browser('firefox', headless=False)
CH  = Browser('chrome' , headless=False)
FFH = Browser('firefox', headless=True)
# NOTE: sadly headless chrome doesn't support extensions..
# https://stackoverflow.com/a/45372648/706389
# there is some workaround, but it's somewhat tricky...
# https://stackoverflow.com/a/46475980/706389


# TODO ugh, I guess it's not that easy to make it work because of isAndroid checks...
# I guess easy way to test if you really want is to temporary force isAndroid to return true in extension...
FM  = Browser('firefox-mobile', headless=False)


def browser_(driver):
    name = driver.name
    # TODO figure out headless??
    if name == 'firefox':
        return FF
    elif name == 'chrome':
        return CH
    else:
        raise AssertionError(driver)


def get_addon_path(kind: str) -> Path:
    # TODO compile first?
    addon_path = (Path(__file__).parent.parent / 'extension' / 'dist' / kind).absolute()
    assert addon_path.exists()
    assert (addon_path / 'manifest.json').exists()
    return addon_path


def get_hotkey(driver, cmd: str) -> str:
    # TODO shit, need to unify this...
    if driver.name == 'chrome':
        chrome_profile = Path(driver.capabilities['chrome']['userDataDir'])
        prefs_file = chrome_profile / 'Default/Preferences'
        import json
        prefs = json.loads(prefs_file.read_text())
        # "commands": {
        #        "linux:Ctrl+Shift+V": {
        #            "command_name": "show_dots",
        #            "extension": "ceedkmkoeooncekjljapnkkjhldddcid",
        #            "global": false
        #        }
        #    },
        cmd_map = {cmd['command_name']: k.split(':')[-1] for k, cmd in prefs['extensions']['commands'].items()}
    else:
        # TODO remove hardcoding somehow...
        # perhaps should be extracted somewhere..
        cmd_map = {
            Command.SHOW_DOTS        : 'Ctrl+Alt+v',
            '_execute_browser_action': 'Ctrl+Alt+e',
            'search'                 : 'Ctrl+Alt+h',
        }
    return cmd_map[cmd].split('+')


def _get_webdriver(tdir: Path, browser: Browser, extension=True):
    addon = get_addon_path(kind=browser.dist)
    if browser.name == 'firefox':
        profile = webdriver.FirefoxProfile(str(tdir))
        options = webdriver.FirefoxOptions()
        options.headless = browser.headless
        # use firefox from here to test https://www.mozilla.org/en-GB/firefox/developer/
        driver = webdriver.Firefox(profile, options=options)

        # driver = webdriver.Firefox(profile, firefox_binary='/L/soft/firefox-dev/firefox/firefox', options=options)
        # TODO how to pass it here properly?

        if extension:
            driver.install_addon(str(addon), temporary=True)
    elif browser.name == 'chrome':
        # TODO ugh. very hacky...
        assert extension, "TODO add support for extension arg"
        ex = tdir / 'extension.zip'
        files = [x.name for x in addon.iterdir()]
        check_call(['apack', '-q', str(ex), *files], cwd=addon)
        # looks like chrome uses temporary dir for data anyway
        options = webdriver.ChromeOptions()
        options.headless = browser.headless
        options.add_extension(ex)
        driver = webdriver.Chrome(options=options)
    else:
        raise RuntimeError(f'Unexpected browser {browser}')
    return driver


# TODO copy paste from grasp
@contextmanager
def get_webdriver(browser: Browser, extension=True):
    with TemporaryDirectory() as td:
        tdir = Path(td)
        driver = _get_webdriver(tdir, browser=browser, extension=extension)
        try:
            yield driver
        finally:
            driver.quit()


def set_host(*, driver, host: str, port: str):
    ep = driver.find_element_by_id('host_id') # TODO rename to 'backend'?
    ep.clear()
    ep.send_keys(f'{host}:{port}')


def save_settings(driver):
    se = driver.find_element_by_id('save_id')
    se.click()

    driver.switch_to.alert.accept()


LOCALHOST = 'http://localhost'


def configure(
        driver,
        *,
        host: Optional[str]=LOCALHOST,
        port: Optional[str]=None,
        show_dots: bool=True,
        highlights: Optional[bool]=None,
        blacklist=None,
        notification: Optional[bool]=None,
        position: Optional[str]=None,
        verbose_errors: bool=True,
):
    def set_checkbox(cid: str, value: bool):
        cb = driver.find_element_by_id(cid)
        selected = cb.is_selected()
        if selected != value:
            cb.click()


    # TODO log properly
    print(f"Setting: port {port}, show_dots {show_dots}")

    open_extension_page(driver, page='options_page.html')
    sleep(1) # err, wtf? otherwise not always interacts with the elements correctly

    assert not (host is None) ^ (port is None), (host, port)
    if host is not None:
        assert port is not None
        set_host(driver=driver, host=host, port=port)

    # dots = driver.find_element_by_id('dots_id')
    # if dots.is_selected() != show_dots:
    #     dots.click()
    # assert dots.is_selected() == show_dots

    # TODO not sure, should be False for demos?
    set_checkbox('verbose_errors_id', verbose_errors)

    if highlights is not None:
        set_checkbox('highlight_id', highlights)

    if notification is not None:
        set_checkbox('contexts_popup_id', notification)

    if position is not None:
        set_position(driver, position)

    if blacklist is not None:
        bl = driver.find_element_by_id('blacklist_id') # .find_element_by_tag_name('textarea')
        bl.click()
        # ugh, that's hacky. presumably due to using Codemirror?
        bla = driver.switch_to_active_element()
        bla.send_keys('\n'.join(blacklist))

    save_settings(driver)


# legacy name
configure_extension = configure


def get_window_id(driver):
    if driver.name == 'firefox':
        pid = str(driver.capabilities['moz:processID'])
    else:
        # ugh nothing in capabilities...
        pid = check_output(['pgrep', '-f', 'chrome.*enable-automation']).decode('utf8').strip()
    # https://askubuntu.com/a/385037/427470
    return get_wid_by_pid(pid)


def get_wid_by_pid(pid: str):
    wids = check_output(['xdotool', 'search', '--pid', pid]).decode('utf8').splitlines()
    wids = [w.strip() for w in wids if len(w.strip()) > 0]

    def has_wm_desktop(wid: str) -> bool:
        # TODO no idea why is that important. found out experimentally
        out = check_output(['xprop', '-id', wid, '_NET_WM_DESKTOP']).decode('utf8')
        return 'not found' not in out

    [wid] = filter(has_wm_desktop, wids)
    return wid


def focus_browser_window(driver):
    wid = get_window_id(driver)
    check_call(['xdotool', 'windowactivate', wid])


def trigger_callback(driver, callback):
    focus_browser_window(driver)
    sleep(0.5)
    callback()


def send_key(key):
    if isinstance(key, str):
        key = key.split('+')

    print(f"sending hotkey! {key}")
    import pyautogui # type: ignore
    pyautogui.hotkey(*key)


def trigger_hotkey(driver, hotkey):
    trigger_callback(driver, lambda: send_key(hotkey))


def trigger_command(driver, cmd):
    trigger_hotkey(driver, get_hotkey(driver, cmd))


class TestHelper(NamedTuple):
    driver: webdriver.Remote

    def open_page(self, page: str) -> None:
        open_extension_page(self.driver, page)

    def move_to(self, element):
        from selenium.webdriver.common.action_chains import ActionChains # type: ignore
        ActionChains(self.driver).move_to_element(element).perform()

    def switch_to_sidebar(self):
        self.driver.switch_to.default_content()
        self.driver.switch_to.frame('promnesia-sidebar')

    def command(self, cmd):
        trigger_command(self.driver, cmd)

    def activate(self):
        self.command(Command.ACTIVATE)

    def mark_visited(self):
        self.command(Command.SHOW_DOTS)

    def wid(self) -> str:
        return get_window_id(self.driver)

    def screenshot(self, path):
        # ugh, webdriver's save_screenshot doesn't behave well with frames
        check_call(['import', '-window', self.wid(), path])


def confirm(what: str):
    import click # type: ignore
    click.confirm(what, abort=True)


@contextmanager
def _test_helper(tmp_path, indexer, test_url: Optional[str], show_dots: bool=False, browser: Browser=FFH):
    tdir = Path(tmp_path)

    indexer(tdir)
    with wserver(db=tdir / 'promnesia.sqlite') as srv, get_webdriver(browser=browser) as driver:
        port = srv.port
        configure_extension(driver, port=port, show_dots=show_dots)
        sleep(0.5)

        if test_url is not None:
            driver.get(test_url)
            sleep(3)
        else:
            driver.get('about:blank')

        yield TestHelper(driver=driver)

class Command:
    SHOW_DOTS = 'mark_visited'
    ACTIVATE  = '_execute_browser_action'
    SEARCH    = 'search'
# TODO assert this against manifest?


def browsers(*br):
    from functools import wraps
    def dec(f):
        @pytest.mark.with_browser
        @pytest.mark.parametrize('browser', br, ids=lambda b: b.dist.replace('-', '_') + ('_headless' if b.headless else ''))
        @wraps(f)
        def ff(*args, **kwargs):
            return f(*args, **kwargs)
        return ff
    return dec


PYTHON_DOC_URL = 'file:///usr/share/doc/python3/html/index.html'


@browsers(FFH, CH)
def test_installs(tmp_path, browser):
    browser.skip_ci_x()

    with get_webdriver(browser=browser):
        # just shouldn't crash
        pass


@browsers(FFH, CH)
def test_settings(tmp_path, browser):
    browser.skip_ci_x()

    # TODO fixture for driver?
    with get_webdriver(browser=browser) as driver:
        configure_extension(driver, port='12345', show_dots=False)
        driver.get('about:blank')
        open_extension_page(driver, page='options_page.html')
        hh = driver.find_element_by_id('host_id')
        assert hh.get_attribute('value') == 'http://localhost:12345'


@browsers(FFH, FF, CH)
def test_backend_status(tmp_path, browser):
    browser.skip_ci_x()

    with get_webdriver(browser=browser) as driver:
        open_extension_page(driver, page='options_page.html')
        sleep(1) # ugh. for some reason pause here seems necessary..
        set_host(driver=driver, host='https://nosuchhost.com', port='1234')
        driver.find_element_by_id('backend_status_id').click()
        sleep(1 + 0.5) # needs enough time for timeout to trigger...

        alert = driver.switch_to.alert
        assert 'ERROR' in alert.text

        # TODO ugh, not sure why it just stucks on headless...
        # perhaps use policy instead? https://stackoverflow.com/a/43946973/706389
        if not browser.headless:
            driver.switch_to.alert.accept()
            sleep(0.5)
            # ugh. extra alert...
            driver.switch_to.alert.accept()

        # TODO implement positive check??

def set_position(driver, settings: str):
    browser = browser_(driver)

    # TODO figure out browser from driver??
    field = driver.find_element_by_xpath('//*[@id="position_css_id"]')
    if browser.name == 'chrome':
        # ugh... for some reason wouldn't send the keys...
        field.click()
        import pyautogui # type: ignore
        # it usually ends up in the middle of the area...
        pyautogui.press(['backspace'] * 500 + ['delete'] * 500)
        pyautogui.typewrite(settings, interval=0.05)
    else:
        area = field.find_element_by_xpath('.//textarea')
        area.send_keys([Keys.DELETE] * 1000)
        area.send_keys(settings)



@browsers(FF, CH)
def test_sidebar_bottom(browser):
    browser.skip_ci_x()

    with get_webdriver(browser=browser) as driver:
        open_extension_page(driver, page='options_page.html')
        sleep(1) # ugh. for some reason pause here seems necessary..

        # for some reason area.clear() caused
        # selenium.common.exceptions.ElementNotInteractableException: Message: Element <textarea> could not be scrolled into view

        settings = """
#promnesia-sidebar {
    --bottom: 1;
    --size: 20%;
}"""

        set_position(driver, settings)

        save_settings(driver)

        driver.get(PYTHON_DOC_URL)

        trigger_command(driver, Command.ACTIVATE)
        confirm("You should see sidebar below")


@uses_x
@browsers(FF, CH)
def test_blacklist_custom(tmp_path, browser):
    # TODO make confirm a fixture? so we can automatically skip them on ci
    with get_webdriver(browser=browser) as driver:
        configure_extension(driver, port='12345', blacklist=('stackoverflow.com',))
        driver.get('http://stackoverflow.com')
        trigger_command(driver, Command.ACTIVATE)
        confirm('page should be blacklisted (black icon), your should see an error notification')


@uses_x
@browsers(FF, CH)
def test_blacklist_builtin(tmp_path, browser):
    with get_webdriver(browser=browser) as driver:
        configure_extension(driver, port='12345')
        driver.get('https://www.hsbc.co.uk/mortgages/')
        confirm('page should be blacklisted (black icon)')


@uses_x
@browsers(FF, CH)
def test_add_to_blacklist(tmp_path, browser):
    with get_webdriver(browser=browser) as driver:
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
        pyautogui.typewrite(['up'] + ['up'] * offset + ['enter'] + ['enter'], interval=0.5)

        confirm('shows prompt with alert to enter pattern to block?')
        driver.switch_to.alert.accept()
        # ugh, seems necessary to guard with sleep; otherwise racey
        sleep(0.5)

        driver.get(driver.current_url)
        confirm('page should be blacklisted (black icon)')


@uses_x
@browsers(FF, CH)
def test_visits(tmp_path, browser):
    test_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    # test_url = "file:///usr/share/doc/python3/html/library/contextlib.html" # TODO ??
    with _test_helper(tmp_path, index_hypothesis, test_url, browser=browser) as helper:
        trigger_command(helper.driver, Command.ACTIVATE)
        confirm('you should see hypothesis contexts')


@uses_x
@browsers(FF, CH)
def test_search_around(tmp_path, browser):
    # TODO it actually lacks a proper end-to-end test withing browser... although I do have something in automatic demos?
    test_url = "about:blank"
    with _test_helper(tmp_path, index_hypothesis, test_url, browser=browser) as h:
        # TODO hmm. dunno if we want to highlight only result with the same timestamp, or the results that are 'near'??
        ts = int(datetime.strptime("2017-05-22T10:59:12.082375+00:00", '%Y-%m-%dT%H:%M:%S.%f%z').timestamp())
        h.open_page(f'search.html?utc_timestamp={ts}')
        confirm('you should see search results, "anthrocidal" should be highlighted red')


# TODO skip if not my hostname
@uses_x
@browsers(FF, CH)
def test_chrome_visits(tmp_path, browser):
    test_url = "https://en.wikipedia.org/wiki/Amplituhedron"
    test_url = "https://en.wikipedia.org/wiki/Symplectic_vector_space"
    with _test_helper(tmp_path, index_local_chrome, test_url, browser=browser) as helper:
        trigger_command(helper.driver, Command.ACTIVATE)
        confirm("You shoud see chrome visits now; with time spent")


@uses_x
@browsers(FF, CH)
def test_show_dots(tmp_path, browser):
    visited = {
        'https://en.wikipedia.org/wiki/Special_linear_group': None,
        'http://en.wikipedia.org/wiki/Unitary_group'        : None,
        'en.wikipedia.org/wiki/Transpose'                   : None,
    }
    test_url = "https://en.wikipedia.org/wiki/Symplectic_group"
    with _test_helper(tmp_path, index_urls(visited), test_url, show_dots=True, browser=browser) as helper:
        trigger_command(helper.driver, Command.SHOW_DOTS)
        confirm("You should see dots near special linear group, Unitary group, Transpose")


@uses_x
@browsers(FF, CH)
def test_search(tmp_path, browser):
    test_url = "https://en.wikipedia.org/wiki/Symplectic_vector_space"
    with _test_helper(tmp_path, index_local_chrome, test_url, browser=browser) as helper:
        trigger_command(helper.driver, Command.SEARCH)
        # TODO actually search something?
        # TODO use current domain as deafult? or 'parent' url?
        confirm("You shoud see search prompt now, with focus on search field")


@uses_x
@browsers(FF, CH)
def test_new_background_tab(tmp_path, browser):
    start_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    # bg_url_text = "El Proceso (The Process)"
    # TODO generate some fake data instead?
    with _test_helper(tmp_path, index_hypothesis, start_url, browser=browser) as helper:
        confirm('you should see notification about contexts')
        helper.driver.find_element(By.XPATH, '//div[@class="logo"]/a').send_keys(Keys.CONTROL + Keys.ENTER)
        confirm('you should not see any new notifications')
        # TODO switch to new tab?
        # TODO https://www.e-flux.com/journal/53/


@uses_x
# TODO shit disappears on chrome and present on firefox
@browsers(FF, CH)
def test_local_page(tmp_path, browser):
    tutorial = 'file:///usr/share/doc/python3/html/tutorial/index.html'
    urls = {
         tutorial                                                : 'TODO read this',
        'file:///usr/share/doc/python3/html/reference/index.html': None,
    }
    url = PYTHON_DOC_URL
    with _test_helper(tmp_path, index_urls(urls), url, browser=browser) as helper:
        confirm('grey icon')
        helper.driver.get(tutorial)
        confirm('green icon. MANUALLY: ACTIVATE SIDEBAR!. It should open sidebar with one visit')
        helper.driver.back()
        # TODO it's always guaranteed to work? https://stackoverflow.com/questions/27626783/python-selenium-browser-driver-back
        confirm('grey icon, should be no sidebar')
        helper.driver.forward()
        confirm('green icon, sidebar visible')


@uses_x
@browsers(FF, CH)
def test_unreachable(tmp_path, browser):
    url = 'https://somenonexist1ngurl.com'
    urls = {
        url: 'some context',
    }
    with _test_helper(tmp_path, index_urls(urls), 'about:blank', browser=browser) as helper:
        try:
            helper.driver.get(url)
        except:
            # results in exception because it's unreachable
            pass
        confirm('green icon, no errors, desktop notification with contexts')


@uses_x
@browsers(FF, CH)
def test_stress(tmp_path, browser):
    page = tmp_path / 'dummy.html'
    page.write_text('''
<html>
<head>HI</head>
<body>test</body>
</html>
    ''')
    url = f'file://{page}'

    urls = [
        (url, f'ctx {i}' if i < 20 else None) for i in range(10000)
    ]
    with _test_helper(tmp_path, index_urls(urls), url, browser=browser) as helper:
        # TODO so, should the response be immediate?
        # TODO shouldn't do any work if we don't open the sidebar
        confirm('is performance reasonable?')

    

@uses_x
@browsers(FF, CH)
def test_fuzz(tmp_path, browser):
    # TODO ugh. this still results in 'tab permissions' pages, but perhaps because of closed tabs?
    # dunno if it's worth fixing..
    urls = {
        'https://www.iana.org/domains/reserved': 'IANA',
        'iana.org/domains/reserved': 'IANA2',
    }
    with _test_helper(tmp_path, index_urls(urls), 'https://example.com', browser=browser) as helper:
        driver = helper.driver
        tabs = 30
        for _ in range(tabs):
            driver.find_element_by_tag_name('a').send_keys(Keys.CONTROL + Keys.RETURN)

        sleep(5)
        for _ in range(tabs - 2):
            driver.close()
            sleep(0.1)
            driver.switch_to.window(driver.window_handles[0])

        def cb():
            for _ in range(10):
                send_key('Ctrl+Shift+t')
                sleep(0.1)
        trigger_callback(driver, cb)
        confirm("shouldn't result in 'unexpected error occured'; show only show single notification per page")


def trigger_sidebar_search(driver):
    driver.switch_to.default_content()
    driver.switch_to.frame('promnesia-sidebar')
    search_button = driver.find_element_by_xpath('//button[text()="Search"]')
    search_button.click()


@uses_x
@browsers(FF, CH)
def test_duplicate_background_pages(tmp_path, browser):
    url = PYTHON_DOC_URL
    with _test_helper(tmp_path, index_urls({}), url, browser=browser) as helper:
        driver = helper.driver

        trigger_command(driver, Command.ACTIVATE)
        # TODO separate test just for buttons from extension
        confirm('sidebar opened?')

        trigger_sidebar_search(driver)
        sleep(1)
        driver.switch_to.window(driver.window_handles[0])
        sleep(1)

        trigger_sidebar_search(driver)
        sleep(1)
        driver.switch_to.window(driver.window_handles[0])
        sleep(1)

        confirm('only two search pages should be opened')

        trigger_command(driver, Command.ACTIVATE)

        confirm('sidebar should be closed now')

        # TODO wtf? browser with search pages stays open after test... 

        # TODO getting this in chrome inspector while running this...
# VM2048 common.js:116 [background] [object Object]
# log @ VM2048 common.js:116
# notifyError @ VM2056 notifications.js:40
# Promise.catch (async)
# (anonymous) @ VM2056 notifications.js:49
# VM2056 notifications.js:17 Uncaught (in promise) TypeError: Cannot read property 'create' of undefined
#     at notify (VM2056 notifications.js:17)
#     at notifyError (VM2056 notifications.js:41)



# TODO FIXME need to test racey conditions _while_ page is loading, results in this 'unexpected error occured'?


# TODO shit, sometimes I have 'bindSidebarData is not defined'? with vebose errors on demo_how_did_i_get_here
