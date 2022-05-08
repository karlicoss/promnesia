#!/usr/bin/env python3
from contextlib import contextmanager
import json
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory
import os
from subprocess import check_call, check_output
from time import sleep
from typing import NamedTuple, Optional, Iterator

import pytest # type: ignore

if __name__ == '__main__':
    # TODO ugh need to figure out PATH
    # python3 -m pytest -s tests/server_test.py::test_query
    pytest.main(['-s', __file__])


from selenium import webdriver # type: ignore
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait as Wait
from selenium.webdriver.support import expected_conditions as EC


from common import under_ci, uses_x, has_x
from integration_test import index_hypothesis, index_local_chrome, index_urls
from server_test import wserver
from browser_helper import open_extension_page, get_cmd_hotkey

from promnesia.logging import LazyLogger


logger = LazyLogger('promnesia-tests')


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
    cmd_map = None
    if driver.name == 'firefox':
        # TODO remove hardcoding somehow...
        # perhaps should be extracted somewhere..
        cmd_map = {
            Command.MARK_VISITED     : 'Ctrl+Alt+v',
            '_execute_browser_action': 'Ctrl+Alt+e',
            'search'                 : 'Ctrl+Alt+h',
        }
    return get_cmd_hotkey(driver, cmd=cmd, cmd_map=cmd_map)


def _get_webdriver(tdir: Path, browser: Browser, extension=True):
    addon = get_addon_path(kind=browser.dist)
    if browser.name == 'firefox':
        options = webdriver.FirefoxOptions()
        options.set_preference('profile', str(tdir))
        options.headless = browser.headless
        # use firefox from here to test https://www.mozilla.org/en-GB/firefox/developer/
        driver = webdriver.Firefox(options=options)
        # todo pass firefox-dev binary?
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


def set_host(*, driver, host: Optional[str], port: Optional[str]) -> None:
    # todo rename to 'backend_id'?
    if host is None:
        ep = driver.find_element(By.ID, 'host_id')
        ep.clear()
        return
    assert port is not None
    ep = driver.find_element(By.ID, 'host_id')
    ep.clear()
    ep.send_keys(f'{host}:{port}')


def save_settings(driver):
    se = driver.find_element(By.ID, 'save_id')
    se.click()

    driver.switch_to.alert.accept()


LOCALHOST = 'http://localhost'


def configure_extension(
        driver,
        *,
        host: Optional[str]=LOCALHOST,
        port: Optional[str]=None,
        show_dots: bool=True,
        highlights: Optional[bool]=None,
        blacklist=None,
        excludelists=None,
        notify_contexts: Optional[bool]=None,
        position: Optional[str]=None,
        verbose_errors: bool=True,
) -> None:
    def set_checkbox(cid: str, value: bool):
        cb = driver.find_element(By.ID, cid)
        selected = cb.is_selected()
        if selected != value:
            cb.click()


    # TODO log properly
    print(f"Setting: port {port}, show_dots {show_dots}")

    open_extension_page(driver, page='options_page.html')
    sleep(1) # err, wtf? otherwise not always interacts with the elements correctly

    set_host(driver=driver, host=host, port=port)

    # dots = driver.find_element(By.ID, 'dots_id')
    # if dots.is_selected() != show_dots:
    #     dots.click()
    # assert dots.is_selected() == show_dots

    # TODO not sure, should be False for demos?
    set_checkbox('verbose_errors_id', verbose_errors)

    if highlights is not None:
        set_checkbox('highlight_id', highlights)

    if notify_contexts is not None:
        set_checkbox('contexts_popup_id', notify_contexts)

    if position is not None:
        set_position(driver, position)

    if blacklist is not None:
        bl = driver.find_element(By.ID, 'global_excludelist_id') # .find_element_by_tag_name('textarea')
        bl.click()
        # ugh, that's hacky. presumably due to using Codemirror?
        bla = driver.switch_to.active_element
        # ugh. doesn't work, .text always returns 0...
        # if len(bla.text) > 0:
        # for some reason bla.clear() isn't working...
        # results in ElementNotInteractableException: Element <textarea> could not be scrolled into view
        bla.send_keys(Keys.CONTROL + 'a')
        bla.send_keys(Keys.BACKSPACE)
        bla.send_keys('\n'.join(blacklist))

    if excludelists is not None:
        excludelists_json = json.dumps(excludelists)

        bl = driver.find_element(By.ID, 'global_excludelists_ext_id') # .find_element_by_tag_name('textarea')
        bl.click()
        # ugh, that's hacky. presumably due to using Codemirror?
        bla = driver.switch_to.active_element
        # ugh. doesn't work, .text always returns 0...
        # if len(bla.text) > 0:
        # for some reason bla.clear() isn't working...
        # results in ElementNotInteractableException: Element <textarea> could not be scrolled into view
        bla.send_keys(Keys.CONTROL + 'a')
        bla.send_keys(Keys.BACKSPACE)
        bla.send_keys(excludelists_json)

    save_settings(driver)


# legacy name
configure = configure_extension


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


def is_headless(driver) -> bool:
    if driver.name == 'firefox':
        return driver.capabilities.get('moz:headless', False)
    else:
        return False


# TODO move to common or something
def trigger_hotkey(driver, hotkey: str) -> None:
    headless = is_headless(driver)
    try:
        trigger_callback(driver, lambda: send_key(hotkey))
    except Exception as e:
        if headless:
            raise RuntimeError("Likely failed because the browser is headless") from e
        else:
            raise e


def trigger_command(driver, cmd: str) -> None:
    if is_headless(driver):
        assert cmd == Command.ACTIVATE, cmd  # will support the rest later..
        # see background-injector.js
        driver.execute_script("""
        var event = document.createEvent('HTMLEvents');
        event.initEvent('selenium-bridge-activate', true, true);
        document.dispatchEvent(event);
        """)
    else:
        trigger_hotkey(driver, get_hotkey(driver, cmd))


class TestHelper(NamedTuple):
    driver: webdriver.Remote

    def open_page(self, page: str) -> None:
        open_extension_page(self.driver, page)

    def move_to(self, element):
        from selenium.webdriver.common.action_chains import ActionChains # type: ignore
        ActionChains(self.driver).move_to_element(element).perform()

    def switch_to_sidebar(self, wait=False):
        self.driver.switch_to.default_content()

        frame_id = 'promnesia-frame'
        frame = None
        if wait:
            Wait(self.driver, timeout=5).until(
                EC.presence_of_element_located((By.ID, frame_id))
            )
        self.driver.switch_to.frame(frame_id)

    @contextmanager
    def sidebar(self, wait=False):
        try:
            self.switch_to_sidebar(wait=wait)
            if wait: # meh
                yield self.driver.find_element_by_id('promnesia-sidebar')
            else:
                yield None
        finally:
            self.driver.switch_to.default_content()

    def command(self, cmd):
        trigger_command(self.driver, cmd)

    def activate(self) -> None:
        self.command(Command.ACTIVATE)

    def mark_visited(self) -> None:
        self.command(Command.MARK_VISITED)

    def wid(self) -> str:
        return get_window_id(self.driver)

    def screenshot(self, path):
        # ugh, webdriver's save_screenshot doesn't behave well with frames
        check_call(['import', '-window', self.wid(), path])


def confirm(what: str) -> None:
    is_headless = 'headless' in os.environ.get('PYTEST_CURRENT_TEST', '')
    if is_headless:
        # ugh.hacky
        Headless().confirm(what)
        return

    import click # type: ignore
    click.confirm(click.style(what, blink=True, fg='yellow'), abort=True)


class Manual:
    def confirm(self, what: str) -> None:
        raise NotImplementedError

class Interactive(Manual):
    def confirm(self, what: str) -> None:
        confirm(what)

class Headless(Manual):
    def confirm(self, what: str) -> None:
        logger.warning('"%s": headless mode, responding "yes"', what)


'''
Helper for tests that are not yet fully automated and require a human to check...
- if running with the GUI, will be interactive
- if running in headless mode, will automatically assume 'yes'.
  of course it's not very robust, but at least we're testing some codepaths then
'''
manual = Interactive() if has_x() else Headless()


@contextmanager
def _test_helper(tmp_path, indexer, test_url: Optional[str], browser: Browser=FFH, **kwargs):
    tdir = Path(tmp_path)

    indexer(tdir)
    with wserver(db=tdir / 'promnesia.sqlite') as srv, get_webdriver(browser=browser) as driver:
        port = srv.port
        configure(driver, port=port, **kwargs)
        sleep(0.5)

        if test_url is not None:
            driver.get(test_url)
            sleep(3) # todo use some condition...
        else:
            driver.get('about:blank')

        yield TestHelper(driver=driver)

class Command:
    MARK_VISITED = 'mark_visited'
    ACTIVATE  = '_execute_browser_action'
    SEARCH    = 'search'
# TODO assert this against manifest?


WITH_BROWSER_TESTS = 'WITH_BROWSER_TESTS'

with_browser_tests = pytest.mark.skipif(
    WITH_BROWSER_TESTS not in os.environ,
    reason=f'set env var {WITH_BROWSER_TESTS}=true if you want to run this test',
)


def browsers(*br: Browser):
    if len(br) == 0:
        br = (FF, FFH, CH)
    if not has_x():
        br = tuple(b for b in br if b.headless)

    from functools import wraps
    def dec(f):
        if len(br) == 0:
            dec_ = pytest.mark.skip('Filtered out all browsers (because of no GUI/non-interactive mode)')
        else:
            dec_ = pytest.mark.parametrize('browser', br, ids=lambda b: b.dist.replace('-', '_') + ('_headless' if b.headless else ''))
        @with_browser_tests
        @dec_
        @wraps(f)
        def ff(*args, **kwargs):
            return f(*args, **kwargs)
        return ff
    return dec


PYTHON_DOC_URL = 'file:///usr/share/doc/python3/html/index.html'


@browsers()
def test_installs(tmp_path, browser):
    with get_webdriver(browser=browser):
        # just shouldn't crash
        pass


@browsers()
def test_settings(tmp_path, browser):
    # TODO fixture for driver?
    with get_webdriver(browser=browser) as driver:
        configure_extension(driver, port='12345', show_dots=False)
        driver.get('about:blank')
        open_extension_page(driver, page='options_page.html')
        hh = driver.find_element(By.ID, 'host_id')
        assert hh.get_attribute('value') == 'http://localhost:12345'


@browsers()
def test_backend_status(tmp_path, browser):
    with get_webdriver(browser=browser) as driver:
        helper = TestHelper(driver)
        helper.open_page('options_page.html')
        sleep(1) # ugh. for some reason pause here seems necessary..

        set_host(driver=driver, host='https://nosuchhost.com', port='1234')
        driver.find_element(By.ID, 'backend_status_id').click()
        sleep(1 + 0.5) # needs enough time for timeout to trigger...

        alert = driver.switch_to.alert
        assert 'ERROR' in alert.text

        sleep(0.5) #  don't remember if needed?
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


@browsers()
def test_sidebar_bottom(browser):
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


@browsers()
def test_blacklist_custom(tmp_path: Path, browser: Browser) -> None:
    with get_webdriver(browser=browser) as driver:
        helper = TestHelper(driver)
        configure_extension(driver, port='12345', blacklist=('stackoverflow.com',))
        driver.get('https://stackoverflow.com/questions/27215462')

        helper.activate()

        manual.confirm('page should be blacklisted (black icon), your should see an error notification')

        # make sure we can't open sidebar for blacklisted page
        # meh, but that'll do for now
        from selenium.common.exceptions import NoSuchFrameException
        with pytest.raises(NoSuchFrameException):
            with helper.sidebar():
                pass

        # reset blacklist
        # also running without backend here, so need to set host to none as well
        configure_extension(driver, host=None, blacklist=())
        driver.back() # TODO maybe configure_extension should go back instead...
        driver.refresh()

        with helper.sidebar(wait=True):
            # at least shouln't fail
            pass

        manual.confirm('sidebar should be visible')


@browsers()
def test_blacklist_builtin(tmp_path: Path, browser: Browser) -> None:
    with get_webdriver(browser=browser) as driver:
        helper = TestHelper(driver)
        configure_extension(driver, port='12345')
        driver.get('https://www.hsbc.co.uk/mortgages/')

        helper.activate()

        manual.confirm('page should be blacklisted (black icon), your should see an error notification')

        # make sure we can't open sidebar for blacklisted page
        # meh, but that'll do for now
        from selenium.common.exceptions import NoSuchFrameException
        with pytest.raises(NoSuchFrameException):
            with helper.sidebar():
                pass

        # reset blacklist
        # also running without backend here, so need to set host to none as well
        configure_extension(driver, host=None, excludelists=())
        driver.back() # TODO maybe configure_extension should go back instead...
        driver.refresh()

        with helper.sidebar(wait=True):
            # at least shouln't fail
            pass

        manual.confirm('sidebar should be visible')


@browsers(FF, CH)
def test_add_to_blacklist(tmp_path, browser):
    with get_webdriver(browser=browser) as driver:
        configure_extension(driver, port='12345')
        driver.get('https://example.com')
        chain = webdriver.ActionChains(driver)
        chain.move_to_element(driver.find_element(By.TAG_NAME, 'h1')).context_click().perform()

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



# todo might be nice to run soft asserts for this test?
@browsers()
def test_visits(tmp_path: Path, browser: Browser) -> None:
    test_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    # test_url = "file:///usr/share/doc/python3/html/library/contextlib.html" # TODO ??
    with _test_helper(tmp_path, index_hypothesis, test_url, browser=browser) as helper:
        driver = helper.driver
        with helper.sidebar():
            # hmm not sure how come it returns anything at all.. but whatever
            srcs = driver.find_elements_by_class_name('src')
            for s in srcs:
                assert not s.is_displayed(), s
            assert len(srcs) >= 8, srcs
            # todo ugh, need to filter out filters, how to only query the ones in the sidebar?

        helper.activate()

        with helper.sidebar(wait=True) as sidebar:
            assert sidebar is not None

            confirm('you should see hypothesis contexts')

            link = driver.find_element_by_partial_link_text('how_algorithms_shape_our_world')
            assert link.is_displayed(), link

            contexts = helper.driver.find_elements_by_class_name('context')
            for c in contexts:
                assert c.is_displayed(), c
            assert len(contexts) == 8


        helper.activate()
        # todo wait till it disappears properly?
        sleep(0.5)

        with helper.sidebar():
            # hmm not sure how come it returns anything at all.. but whatever
            srcs = driver.find_elements_by_class_name('src')
            for s in srcs:
                assert not s.is_displayed(), s


@browsers()
def test_search_around(tmp_path, browser) -> None:
    # TODO it actually lacks a proper end-to-end test within browser... although I do have something in automatic demos?
    test_url = "about:blank"
    with _test_helper(tmp_path, index_hypothesis, test_url, browser=browser) as h:
        # TODO hmm. dunno if we want to highlight only result with the same timestamp, or the results that are 'near'??
        ts = int(datetime.strptime("2017-05-22T10:59:12.082375+00:00", '%Y-%m-%dT%H:%M:%S.%f%z').timestamp())
        h.open_page(f'search.html?utc_timestamp_s={ts}')
        manual.confirm('you should see search results, "anthrocidal" should be highlighted red')
        # FIXME test clicking search around in actual search page.. it didn't work, seemingly because of initBackground() handling??


# TODO skip if not my hostname
@uses_x
@browsers(FF, CH)
def test_chrome_visits(tmp_path, browser):
    test_url = "https://en.wikipedia.org/wiki/Amplituhedron"
    test_url = "https://en.wikipedia.org/wiki/Symplectic_vector_space"
    with _test_helper(tmp_path, index_local_chrome, test_url, browser=browser) as helper:
        trigger_command(helper.driver, Command.ACTIVATE)
        confirm("You shoud see chrome visits now; with time spent")


@browsers(FF, CH)
def test_show_visited_marks(tmp_path, browser):
    visited = {
        'https://en.wikipedia.org/wiki/Special_linear_group': None,
        'http://en.wikipedia.org/wiki/Unitary_group'        : None,
        'en.wikipedia.org/wiki/Transpose'                   : None,
    }
    test_url = "https://en.wikipedia.org/wiki/Symplectic_group"
    with _test_helper(tmp_path, index_urls(visited), test_url, show_dots=True, browser=browser) as helper:
        trigger_command(helper.driver, Command.MARK_VISITED)
        confirm("You should see visited marks near special linear group, Unitary group, Transpose")


@browsers(FF, CH)
@pytest.mark.parametrize(
    'url',
    [
        "https://en.wikipedia.org/wiki/Symplectic_group",

        # regression test for https://github.com/karlicoss/promnesia/issues/295
        # note: seemed to reproduce on chrome more consistently for some reason
        "https://www.udemy.com/course/javascript-bible/",
    ],
    ids=[
        'wiki',
        'udemy'
    ],
)
def test_sidebar(tmp_path, browser, url: str) -> None:
    visited = {
        url : 'whatever',
    }
    indexer = index_urls(visited, source_name='ælso test unicode 💩')
    with _test_helper(tmp_path, indexer, url, show_dots=True, browser=browser) as helper:
        trigger_command(helper.driver, Command.ACTIVATE)
        confirm("You should see green icon, also one visit in sidebar. Make sure the unicode is displayed correctly.")


@browsers(FF, CH)
def test_search(tmp_path, browser):
    test_url = "https://en.wikipedia.org/wiki/Symplectic_vector_space"
    with _test_helper(tmp_path, index_hypothesis, test_url, browser=browser) as helper:
        trigger_command(helper.driver, Command.SEARCH)
        # TODO actually search something?
        # TODO use current domain as default? or 'parent' url?
        confirm("You shoud see search prompt now, with focus on search field")


@browsers()
def test_new_background_tab(tmp_path, browser) -> None:
    start_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    # bg_url_text = "El Proceso (The Process)"
    # TODO generate some fake data instead?
    with _test_helper(
            tmp_path, index_hypothesis, start_url, browser=browser,
            notify_contexts=True,
    ) as helper:
        manual.confirm('you should see notification about contexts')
        page_logo = helper.driver.find_element(By.XPATH, '//a[@class="page-logo"]')
        page_logo.send_keys(Keys.CONTROL + Keys.ENTER) # ctrl+click -- opens the link in new background tab
        manual.confirm('you should not see any new notifications')
        # TODO switch to new tab?
        # TODO https://www.e-flux.com/journal/53/


# TODO shit disappears on chrome and present on firefox
@browsers()
def test_local_page(tmp_path: Path, browser: Browser) -> None:
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
        # fIXME fuck. failing here to load anchorme as well as webext-options-sync? ugh.
        helper.driver.forward()
        confirm('green icon, sidebar visible')


@browsers()
def test_unreachable(tmp_path, browser) -> None:
    url = 'https://somenonexist1ngurl.com'
    urls = {
        url: 'some context',
    }
    with _test_helper(
            tmp_path, index_urls(urls), 'about:blank', browser=browser,
            notify_contexts=True,
            verbose_errors=False,
    ) as helper:
        try:
            helper.driver.get(url)
        except:
            # results in exception because it's unreachable
            pass
        # TODO maybe in this case it could instead open the sidebar in a separate tab?
        manual.confirm('green icon, no errors, desktop notification with contexts')


@browsers()
def test_stress(tmp_path, browser) -> None:
    url = 'https://www.reddit.com/'
    urls = [
        (f'{url}/subpath/{i}.html', f'context {i}' if i > 10000 else None) for i in range(50000)
    ]
    with _test_helper(tmp_path, index_urls(urls), url, browser=browser) as helper:
        if has_x():
            helper.activate()

        manual.confirm('''
Is performance reasonable?
The sidebar should show up, and update gradually.
You should be able to scroll the page, trigger tooltips, etc., without any lags.
'''.strip())

    
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
            driver.find_element(By.TAG_NAME, 'a').send_keys(Keys.CONTROL + Keys.RETURN)

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
        # FIXME shows quite a bunch of notifications here...
        confirm("shouldn't result in 'unexpected error occured'; show only show single notification per page")


def trigger_sidebar_search(driver):
    driver.switch_to.default_content()
    driver.switch_to.frame('promnesia-sidebar')
    search_button = driver.find_element_by_xpath('//button[text()="Search"]')
    search_button.click()


@browsers(FF, CH)
def test_duplicate_background_pages(tmp_path, browser):
    url = PYTHON_DOC_URL
    with _test_helper(tmp_path, index_urls({'whatever.coom': '123'}), url, browser=browser) as helper:
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
