#!/usr/bin/env python3
from __future__ import annotations

from contextlib import contextmanager, ExitStack
import json
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory
import os
import shutil
from subprocess import check_call, check_output
from time import sleep
from typing import NamedTuple, Optional, Iterator, TypeVar, Callable, Sequence, Union

import pytest # type: ignore

if __name__ == '__main__':
    # TODO ugh need to figure out PATH
    # python3 -m pytest -s tests/server_test.py::test_query
    pytest.main(['-s', __file__])


from selenium import webdriver
from selenium.webdriver import Remote as Driver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.support.ui import WebDriverWait as Wait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoAlertPresentException, NoSuchFrameException, TimeoutException


from common import under_ci, uses_x, has_x, local_http_server
from integration_test import index_hypothesis, index_local_chrome, index_urls
from server_test import wserver
from browser_helper import open_extension_page, get_cmd_hotkey
from webdriver_utils import frame_context, window_context, is_visible


from promnesia.logging import LazyLogger


logger = LazyLogger('promnesia-tests', level='debug')


from promnesia.common import measure as measure_orig
@contextmanager
def measure(*args, **kwargs):
    kwargs['logger'] = logger
    with measure_orig(*args, **kwargs) as m:
        yield m


class Browser(NamedTuple):
    dist: str
    headless: bool

    @property
    def name(self) -> str:
        return self.dist.split('-')[0] # TODO meh

    def skip_ci_x(self) -> None:
        if under_ci() and not self.headless:
            pytest.skip("Only can't use headless browser on CI")


FF  = Browser('firefox', headless=False)
CH  = Browser('chrome' , headless=False)
FFH = Browser('firefox', headless=True)
CHH = Browser('chrome' , headless=True)


# TODO ugh, I guess it's not that easy to make it work because of isAndroid checks...
# I guess easy way to test if you really want is to temporary force isAndroid to return true in extension...
FM  = Browser('firefox-mobile', headless=False)


def browser_(driver: Driver) -> Browser:
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


def get_hotkey(driver: Driver, cmd: str) -> str:
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


def _get_webdriver(tdir: Path, browser: Browser, extension: bool=True) -> Driver:
    addon = get_addon_path(kind=browser.dist)
    driver: Driver
    if browser.name == 'firefox':
        ff_options = webdriver.FirefoxOptions()
        ff_options.set_preference('profile', str(tdir))
        ff_options.headless = browser.headless
        # use firefox from here to test https://www.mozilla.org/en-GB/firefox/developer/
        driver = webdriver.Firefox(options=ff_options)
        # todo pass firefox-dev binary?
        if extension:
            driver.install_addon(str(addon), temporary=True)
    elif browser.name == 'chrome':
        # TODO ugh. very hacky...
        assert extension, "TODO add support for extension arg"
        ex = tdir / 'extension.zip'
        shutil.make_archive(str(ex.with_suffix('')), format='zip', root_dir=addon)
        # looks like chrome uses temporary dir for data anyway
        cr_options = webdriver.ChromeOptions()
        if browser.headless:
            if 'UNDER_DOCKER' in os.environ:
                # docker runs as root and chrome refuses to use headless in that case
                cr_options.add_argument('--no-sandbox')

            # regular --headless doesn't support extensions for some reason
            cr_options.add_argument('--headless=new')
        cr_options.add_extension(str(ex))
        driver = webdriver.Chrome(options=cr_options)
    else:
        raise RuntimeError(f'Unexpected browser {browser}')
    return driver


# TODO copy paste from grasp
@contextmanager
def get_webdriver(browser: Browser, extension=True) -> Iterator[Driver]:
    with TemporaryDirectory() as td:
        tdir = Path(td)
        driver = _get_webdriver(tdir, browser=browser, extension=extension)
        try:
            yield driver
        finally:
            driver.quit()


def set_host(*, driver: Driver, host: Optional[str], port: Optional[str]) -> None:
    # todo rename to 'backend_id'?
    ep = driver.find_element(By.ID, 'host_id')
    ep.clear()
    # sanity check -- make sure there are no race conditions with async operations
    assert ep.get_attribute('value') == ''
    if host is None:
        return
    assert port is not None
    ep.send_keys(f'{host}:{port}')
    assert ep.get_attribute('value') == f'{host}:{port}'


def _switch_to_alert(driver: Driver) -> Alert:
    """
    Alert is often shown as a result of async operations, so this is to prevent race conditions
    """
    e: Optional[Exception] = None
    for _ in range(100 * 10): # wait 10 secs max
        try:
            return driver.switch_to.alert
        except NoAlertPresentException as ex:
            e = ex
            sleep(0.01)
            continue
    assert e is not None
    raise e


LOCALHOST = 'http://localhost'


def configure_extension(
        driver: Driver,
        *,
        host: Optional[str]=LOCALHOST,
        port: Optional[str]=None,
        show_dots: bool=True,
        highlights: Optional[bool]=None,
        blacklist: Optional[Sequence[str]]=None,
        excludelists: Optional[Sequence[str]]=None,
        notify_contexts: Optional[bool]=None,
        position: Optional[str]=None,
        verbose_errors: bool=True,
) -> None:
    def set_checkbox(cid: str, value: bool) -> None:
        cb = driver.find_element(By.ID, cid)
        selected = cb.is_selected()
        if selected != value:
            cb.click()


    # TODO log properly
    print(f"Setting: port {port}, show_dots {show_dots}")

    helper = TestHelper(driver)
    page = helper.options_page
    page.open()

    set_host(driver=driver, host=host, port=port)

    if show_dots is not None:
        set_checkbox('mark_visited_always_id', show_dots)

    # TODO not sure, should be False for demos?
    set_checkbox('verbose_errors_id', verbose_errors)

    if highlights is not None:
        set_checkbox('highlight_id', highlights)

    if notify_contexts is not None:
        set_checkbox('contexts_popup_id', notify_contexts)

    if position is not None:
        page.set_position(position)

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

    page.save()


# legacy name
configure = configure_extension


def get_window_id(driver: Driver) -> str:
    if driver.name == 'firefox':
        pid = str(driver.capabilities['moz:processID'])
    else:
        # ugh nothing in capabilities...
        pid = check_output(['pgrep', '-f', 'chrome.*enable-automation']).decode('utf8').strip()
    # https://askubuntu.com/a/385037/427470
    return get_wid_by_pid(pid)


def get_wid_by_pid(pid: str) -> str:
    wids = check_output(['xdotool', 'search', '--pid', pid]).decode('utf8').splitlines()
    wids = [w.strip() for w in wids if len(w.strip()) > 0]

    def has_wm_desktop(wid: str) -> bool:
        # TODO no idea why is that important. found out experimentally
        out = check_output(['xprop', '-id', wid, '_NET_WM_DESKTOP']).decode('utf8')
        return 'not found' not in out

    [wid] = filter(has_wm_desktop, wids)
    return wid


def focus_browser_window(driver: Driver) -> None:
    assert not is_headless(driver)  # just in case
    wid = get_window_id(driver)
    check_call(['xdotool', 'windowactivate', '--sync', wid])


def trigger_callback(driver: Driver, callback) -> None:
    focus_browser_window(driver)
    callback()


def send_key(key) -> None:
    if isinstance(key, str):
        key = key.split('+')

    print(f"sending hotkey! {key}")
    import pyautogui # type: ignore
    pyautogui.hotkey(*key)


def is_headless(driver: Driver) -> bool:
    if driver.name == 'firefox':
        return driver.capabilities.get('moz:headless', False)
    elif driver.name == 'chrome':
        # https://antoinevastel.com/bot%20detection/2018/01/17/detect-chrome-headless-v2.html
        return driver.execute_script("return navigator.webdriver") is True
    else:
        raise RuntimeError(driver.name)


# TODO move to common or something
def trigger_hotkey(driver: Driver, hotkey: str) -> None:
    headless = is_headless(driver)
    try:
        trigger_callback(driver, lambda: send_key(hotkey))
    except Exception as e:
        if headless:
            raise RuntimeError("Likely failed because the browser is headless") from e
        else:
            raise e


def trigger_command(driver: Driver, cmd: str) -> None:
    if is_headless(driver):
        ccc = {
            Command.ACTIVATE    : 'selenium-bridge-activate',
            Command.MARK_VISITED: 'selenium-bridge-mark-visited',
            Command.SEARCH      : 'selenium-bridge-search',
        }[cmd]
        # see selenium_bridge.js
        driver.execute_script(f"""
        var event = document.createEvent('HTMLEvents');
        event.initEvent('{ccc}', true, true);
        document.dispatchEvent(event);
        """)
    else:
        trigger_hotkey(driver, get_hotkey(driver, cmd))


PROMNESIA_SIDEBAR_ID = 'promnesia-sidebar'
class Sidebar(NamedTuple):
    driver: Driver
    helper: 'TestHelper'

    @contextmanager
    def ctx(self) -> Iterator[WebElement]:
        selector = (By.XPATH, '//iframe[contains(@id, "promnesia-frame")]')
        wait = 5  # if you want to decrease this, make sure test_sidebar_navigation isn't failing
        frame_element = Wait(self.driver, timeout=wait).until(
            EC.presence_of_element_located(selector),
        )

        frames = self.driver.find_elements(*selector)
        # TODO uncomment it later when sidebar is injected gracefully...
        # assert len(frames) == 1, frames  # just in case

        frame_id = frame_element.get_attribute('id')
        with frame_context(self.driver, frame_id) as frame:
            assert frame is not None
            yield frame

    @property
    def available(self) -> bool:
        try:
            with self.ctx():
                return True
        except TimeoutException:
            return False

    @property
    def visible(self) -> bool:
        loc = (By.ID, PROMNESIA_SIDEBAR_ID)
        with self.ctx():
            Wait(self.driver, timeout=5).until(
                EC.presence_of_element_located(loc)
            )
            # NOTE: document in JS here is in the context of iframe
            return is_visible(self.driver, self.driver.find_element(*loc))

    def open(self) -> None:
        assert not self.visible
        self.helper.activate()

        with measure('Sidebar.open') as m:
            while not self.visible:
                assert m() <= 10, 'timeout'
                sleep(0.001)

    def close(self) -> None:
        assert self.visible
        self.helper.activate()
        with measure('Sidebar.close') as m:
            while self.visible:
                assert m() <= 10, 'timeout'
                sleep(0.001)

    @property
    def filters(self) -> list[WebElement]:
        # TODO hmm this only works within sidebar frame context
        # but if we add with self.ctx() here, it seems unhappy with enterinng the context twice
        # do something about it later..
        outer = self.driver.find_element(By.ID, 'promnesia-sidebar-filters')
        return outer.find_elements(By.CLASS_NAME, 'src')


    @property
    def visits(self) -> list[WebElement]:
        return self.driver.find_elements(By.XPATH, '//*[@id="visits"]/li')

    def trigger_search(self) -> None:
        # this should be the window with extension
        cur_window_handles = self.driver.window_handles
        with self.ctx():
            search_button = self.driver.find_element(By.ID, 'button-search')
            search_button.click()
            self.helper.wait_for_search_tab(cur_window_handles)


class OptionsPage(NamedTuple):
    driver: Driver
    helper: 'TestHelper'

    def set_position(self, settings: str) -> None:
        field = self.driver.find_element(By.XPATH, '//*[@id="position_css_id"]')

        area = field.find_element(By.CLASS_NAME, 'cm-content')
        area.click()

        # for some reason area.clear() caused
        # selenium.common.exceptions.ElementNotInteractableException: Message: Element <textarea> could not be scrolled into view

        def contents() -> str:
            return self.driver.execute_script('return arguments[0].cmView.view.state.doc.toString()', area)

        # TODO FFS. these don't seem to work??
        # count = len(area.get_attribute('value'))
        # and this only returns visible porition of the text??? so only 700 characters or something
        # count = len(field.text)
        # count += 100  # just in case
        count = 3000 # meh
        # focus ends up at some random position, so need both backspace and delete
        area.send_keys([Keys.BACKSPACE] * count + [Keys.DELETE] * count)
        assert contents() == ''
        area.send_keys(settings)

        # just in case, also need to remove spaces to workaround indentation
        assert [l.strip() for l in contents().splitlines()] == [l.strip() for l in settings.splitlines()]

    def open(self) -> None:
        self.helper.open_page('options_page.html')
        # make sure settings are loaded first -- otherwise we might get race conditions when we try to set them in tests
        Wait(self.driver, timeout=5).until(
            EC.presence_of_element_located((By.ID, 'promnesia-settings-loaded'))
        )

    def save(self) -> None:
        se = self.driver.find_element(By.ID, 'save_id')
        se.click()
        _switch_to_alert(self.driver).accept()


class TestHelper(NamedTuple):
    driver: Driver

    def open_page(self, page: str) -> None:
        open_extension_page(self.driver, page)

    def open_options_page(self) -> None:
        self.options_page.open()
        self.open_page('options_page.html')

    def open_search_page(self, query: str="") -> None:
        self.open_page('search.html' + query)

        Wait(self.driver, timeout=10).until(
            EC.presence_of_element_located((By.ID, 'visits')),
        )

    def move_to(self, element) -> None:
        from selenium.webdriver.common.action_chains import ActionChains
        ActionChains(self.driver).move_to_element(element).perform()

    def switch_to_sidebar(self, wait: Union[bool, int]=False, *, wait2: bool=True) -> None:
        raise RuntimeError('not used anymore, use with helper.sidebar instead!')

    @property
    def sidebar(self) -> Sidebar:
        return Sidebar(driver=self.driver, helper=self)

    @property
    def _sidebar(self) -> Sidebar:
        # legacy method
        return self.sidebar

    @property
    def options_page(self) -> OptionsPage:
        return OptionsPage(driver=self.driver, helper=self)

    def command(self, cmd) -> None:
        trigger_command(self.driver, cmd)

    def activate(self) -> None:
        self.command(Command.ACTIVATE)

    def mark_visited(self) -> None:
        self.command(Command.MARK_VISITED)

    def search(self) -> None:
        cur_window_handles = self.driver.window_handles
        self.command(Command.SEARCH)
        # self.wait_for_search_tab(cur_window_handles)

    def wait_for_search_tab(self, cur_window_handles) -> None:
        # for some reason the webdriver's context stays the same even when new tab is opened
        # ugh. not sure why it's so elaborate, but that's what stackoverflow suggested
        Wait(self.driver, timeout=5).until(EC.number_of_windows_to_be(len(cur_window_handles) + 1))
        new_windows = set(self.driver.window_handles) - set(cur_window_handles)
        assert len(new_windows) == 1, new_windows
        [new_window] = new_windows
        self.driver.switch_to.window(new_window)
        Wait(self.driver, timeout=5).until(EC.presence_of_element_located((By.ID, 'promnesia-search')))

    def wid(self) -> str:
        return get_window_id(self.driver)

    def screenshot(self, path: Path) -> None:
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


# TODO deprecate this in favor of run_server
@contextmanager
def _test_helper(tmp_path: Path, indexer: Callable[[Path], None], test_url: Optional[str], browser: Browser, **kwargs) -> Iterator[TestHelper]:
    tdir = Path(tmp_path)

    indexer(tdir)
    with wserver(db=tdir / 'promnesia.sqlite') as srv, get_webdriver(browser=browser) as driver:
        port = srv.port
        configure_extension(driver, port=port, **kwargs)
        sleep(0.5)

        if test_url is not None:
            driver.get(test_url)
            # TODO meh, it's really crap
            sleep(3) # todo use some condition...
        else:
            driver.get('about:blank')

        yield TestHelper(driver=driver)


@contextmanager
def run_server(tmp_path: Path, indexer: Callable[[Path], None], driver: Driver, **kwargs) -> Iterator[TestHelper]:
    # TODO ideally should index in a separate thread? and perhaps start server too
    indexer(tmp_path)
    with wserver(db=tmp_path / 'promnesia.sqlite') as srv:
        # this bit (up to yield) takes about 1.5s -- I guess it's the 1s sleep in configure_extension
        port = srv.port
        configure_extension(driver, port=port, **kwargs)
        driver.get('about:blank')  # not sure if necessary
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


X = TypeVar('X')
IdType = Callable[[X], X]


def browsers(*br: Browser) -> IdType:
    if len(br) == 0:
        br = (FF, FFH, CH, CHH)
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


@pytest.fixture
def driver(browser: Browser) -> Iterator[Driver]:
    with get_webdriver(browser=browser) as d:
        yield d


@browsers()
def test_installs(tmp_path: Path, driver: Driver) -> None:
    """
    Even loading the extension into webdriver is pretty elaborate, so the test just checks it works
    """
    pass


@browsers()
def test_settings(tmp_path: Path, driver: Driver) -> None:
    """
    Just a basic test for opening options page and making sure it loads options
    """
    helper = TestHelper(driver)
    helper.open_options_page()
    hh = driver.find_element(By.ID, 'host_id')
    assert hh.get_attribute('value') == 'http://localhost:13131'  # default

    configure_extension(driver, port='12345', show_dots=False)
    driver.get('about:blank')

    helper.open_options_page()
    hh = driver.find_element(By.ID, 'host_id')
    assert hh.get_attribute('value') == 'http://localhost:12345'


@browsers()
def test_backend_status(tmp_path: Path, driver: Driver) -> None:
    """
    We should get an alert if backend is unavailable on the status check
    """
    helper = TestHelper(driver)
    helper.open_options_page()
    set_host(driver=driver, host='https://nosuchhost.com', port='1234')

    driver.find_element(By.ID, 'backend_status_id').click()

    alert = _switch_to_alert(driver)
    assert 'ERROR' in alert.text
    alert.accept()

    # TODO implement positive check, e.g. when backend is present


@browsers()
def test_sidebar_position(driver: Driver) -> None:
    """
    Checks that default sidebar position is on the right, and that changing it to --bottom: 1 works
    """
    helper = TestHelper(driver)
    options_page = helper.options_page
    options_page.open()
    # TODO WTF; if we don't open extension page once, we can't read out hotkeys from the chrome extension settings file
    # (so e.g. trigger_command isn't working???)

    # TODO hmm maybe need to disable backend here... otherwise it connects to the default backend and might be a bit slow
    driver.get('https://example.com')

    helper._sidebar.open()
    confirm("sidebar: should be displayed on the right (default)")
    helper._sidebar.close()

    options_page.open()
    settings = """
#promnesia-frame {
  --bottom: 1;
  --size: 20%;
}""".strip()
    helper.options_page.set_position(settings)
    options_page.save()

    driver.get('https://example.com')
    helper._sidebar.open()
    confirm("sidebar: should be displayed below")


@browsers()
def test_blacklist_custom(driver: Driver) -> None:
    helper = TestHelper(driver)
    configure_extension(driver, port='12345', blacklist=('stackoverflow.com',))
    driver.get('https://stackoverflow.com/questions/27215462')

    helper.activate()
    manual.confirm('page should be blacklisted (black icon), you should see an error notification')
    # make sure there is not even the frame for blacklisted page
    assert not helper._sidebar.available

    # reset blacklist
    # also running without backend here, so need to set host to none as well
    configure_extension(driver, host=None, blacklist=())
    driver.back()
    driver.refresh()

    helper._sidebar.open()
    manual.confirm('sidebar: should be visible')


@browsers()
def test_blacklist_builtin(driver: Driver) -> None:
    helper = TestHelper(driver)
    configure_extension(driver, port='12345')
    driver.get('https://www.hsbc.co.uk/mortgages/')

    helper.activate()
    manual.confirm('page should be blacklisted (black icon), your should see an error notification')
    # make sure there is not even the frame for blacklisted page
    assert not helper._sidebar.available

    # reset blacklist
    # also running without backend here, so need to set host to none as well
    configure_extension(driver, host=None, excludelists=())
    driver.back()
    driver.refresh()

    helper._sidebar.open()
    manual.confirm('sidebar: should be visible')


@browsers(FF, CH)
def test_add_to_blacklist_context_menu(tmp_path: Path, browser: Browser) -> None:
    # doesn't work on headless because not sure how to interact with context menu.
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
        _switch_to_alert(driver).accept()
        # ugh, seems necessary to guard with sleep; otherwise racey
        sleep(0.5)

        driver.get(driver.current_url)
        confirm('page should be blacklisted (black icon)')


# todo might be nice to run soft asserts for this test?
@browsers()
def test_visits(tmp_path: Path, driver: Driver) -> None:
    test_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    # test_url = "file:///usr/share/doc/python3/html/library/contextlib.html" # TODO ??
    with run_server(tmp_path=tmp_path, indexer=index_hypothesis, driver=driver) as helper:
        driver.get(test_url)
        confirm("sidebar: shouldn't be visible")

        with helper._sidebar.ctx():
            # hmm not sure how come it returns anything at all.. but whatever
            srcs = driver.find_elements(By.CLASS_NAME, 'src')
            for s in srcs:
                # elements should be bound to the sidebar, but aren't displayed yet
                assert not is_visible(driver, s), s
            assert len(srcs) >= 8, srcs
            # todo ugh, need to filter out filters, how to only query the ones in the sidebar?

        helper._sidebar.open()
        confirm('sidebar: you should see hypothesis contexts')

        with helper._sidebar.ctx():
            # sleep(1)
            link = driver.find_element(By.PARTIAL_LINK_TEXT, 'how_algorithms_shape_our_world')
            assert is_visible(driver, link), link

            contexts = helper.driver.find_elements(By.CLASS_NAME, 'context')
            for c in contexts:
                assert is_visible(driver, c), c
            assert len(contexts) == 8

        helper._sidebar.close()
        confirm("sidebar: shouldn't be visible")


@browsers()
def test_search_around(tmp_path: Path, driver: Driver) -> None:
    # TODO hmm. dunno if we want to highlight only result with the same timestamp, or the results that are 'near'??
    ts = int(datetime.strptime("2017-05-22T10:59:12.082375+00:00", '%Y-%m-%dT%H:%M:%S.%f%z').timestamp())
    with run_server(tmp_path=tmp_path, indexer=index_hypothesis, driver=driver) as helper:
        helper.open_search_page(f'?utc_timestamp_s={ts}')

        visits = driver.find_element(By.ID, 'visits')
        sleep(1)  # wait till server responds and renders results
        results = visits.find_elements(By.CSS_SELECTOR, 'li')
        assert len(results) == 9

        hl = visits.find_element(By.CLASS_NAME, 'highlight')
        assert 'anthrocidal' in hl.text

        manual.confirm('you should see search results, "anthrocidal" should be highlighted red')
        # FIXME test clicking search around in actual search page.. it didn't work, seemingly because of initBackground() handling??


# TODO skip if not my hostname
@uses_x
@browsers(FF, CH)
def test_chrome_visits(tmp_path: Path, browser: Browser) -> None:
    pytest.skip('TODO hmm seems that this file is gone now? not sure if a good test anyway')
    test_url = "https://en.wikipedia.org/wiki/Amplituhedron"
    test_url = "https://en.wikipedia.org/wiki/Symplectic_vector_space"
    with _test_helper(tmp_path, index_local_chrome, test_url, browser=browser) as helper:
        trigger_command(helper.driver, Command.ACTIVATE)
        confirm("You shoud see chrome visits now; with time spent")


@browsers()
def test_show_visited_marks(tmp_path: Path, driver: Driver) -> None:
    visited = {
        'https://en.wikipedia.org/wiki/Special_linear_group': None,
        'http://en.wikipedia.org/wiki/Unitary_group'        : None,
        'en.wikipedia.org/wiki/Transpose'                   : None,
    }
    test_url = "https://en.wikipedia.org/wiki/Symplectic_group"
    with run_server(tmp_path=tmp_path, indexer=index_urls(visited), driver=driver, show_dots=False) as helper:
        driver.get(test_url)
        helper.mark_visited()
        sleep(1)  # marks are async, wait till it marks

        slg = driver.find_elements(By.XPATH, '//a[contains(@href, "/wiki/Special_linear_group")]')
        assert len(slg) > 0
        for s in slg:
            assert 'promnesia-visited' in s.get_attribute('class')

        confirm("You should see visited marks near special linear group, Unitary group, Transpose")


@browsers()
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
def test_sidebar_basic(tmp_path: Path, driver: Driver, url: str) -> None:
    if 'udemy' in url:
        pytest.skip('TODO udemy tests are very timing out. Perhaps because of cloudflare protection?')

    visited = {
        # this also tests org-mode style link highlighting (custom anchorme version)
        url : 'whatever\nalso [[https://wiki.openhumans.org/wiki/Personal_Science_Wiki][Personal Science Wiki]]\nmore text',
    }
    src = "ælso test unicode 💩"
    indexer = index_urls(visited, source_name=src)
    with run_server(tmp_path=tmp_path, indexer=indexer, driver=driver, show_dots=True) as helper:
        driver.get(url)
        helper._sidebar.open()

        # a bit crap, but also annoying to indent just to put it in context considering it impacts all of the test...
        # ugh also it doesn't work for some reason..
        # helper._sidebar.ctx().__enter__()

        with helper._sidebar.ctx():
            filters = helper._sidebar.filters
            assert len(filters) == 2, filters

            _all = filters[0]
            tag  = filters[1]

            # this should happen in JS
            sanitized = src.replace(' ', '')

            assert 'all'     in _all.text
            assert sanitized in tag.text

            assert 'all' in _all.get_attribute('class').split()
            assert sanitized in tag.get_attribute('class').split()

            visits = helper._sidebar.visits
            assert len(visits) == 1, visits
            [v] = visits

            assert v.find_element(By.CLASS_NAME, 'src').text == sanitized
            ctx_el = v.find_element(By.CLASS_NAME, 'context')
            assert ctx_el.text == visited[url]
            # make sure linkifying works
            assert ctx_el.find_element(By.TAG_NAME, 'a').get_attribute('href') == 'https://wiki.openhumans.org/wiki/Personal_Science_Wiki'

        confirm("You should see green icon, also one visit in sidebar. Make sure the unicode is displayed correctly.")


@browsers()
def test_search_command(tmp_path: Path, driver: Driver) -> None:
    """
    Basic test that search command handler works and it opens search inteface
    """
    test_url = "https://en.wikipedia.org/wiki/Symplectic_vector_space"
    with run_server(tmp_path=tmp_path, indexer=index_hypothesis, driver=driver) as helper:
        driver.get(test_url)

        helper.search()
        # TODO actually search something?
        # TODO use current domain as default? or 'parent' url?
        confirm("You shoud see search prompt now, with focus on search field")


@browsers()
def test_new_background_tab(tmp_path: Path, browser: Browser) -> None:
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


PYTHON_DOC_PATH = Path('/usr/share/doc/python3/html')


@browsers()
@pytest.mark.parametrize(
    'base_url',
    [
        f'file://{PYTHON_DOC_PATH}',
        'LOCAL',
    ],
    ids=[
        'file',
        'local',
    ],
)
def test_sidebar_navigation(tmp_path: Path, driver: Driver, base_url: str) -> None:
    if 'file:' in base_url and driver.name == 'chrome':
        pytest.skip("TODO used to work, but must have broken after some Chrome update?")
        # seems broken on any local page -- only transparent sidebar frame is shown
        # the issue is that contentDocument.body is null -- no idea why

    if driver.name == 'chrome':
        pytest.skip("TODO need to split the test into version which isn's using back/forward. see https://bugs.chromium.org/p/chromedriver/issues/detail?id=4329")
        # also need to extract a scenario for manual testing I guess

    with ExitStack() as stack:
        if base_url == 'LOCAL':
            local_addr = stack.enter_context(local_http_server(PYTHON_DOC_PATH, port=15454))
            base_url = local_addr


        tutorial  = f'{base_url}/tutorial/index.html'
        reference = f'{base_url}/reference/index.html'
        # reference has a link to tutorial (so will display a context)

        urls = {
            tutorial : 'TODO read this https://please-highligh-this-link.com',
            reference: None,
        }
        indexer = index_urls(urls)
        url = reference

        helper = stack.enter_context(run_server(tmp_path=tmp_path, indexer=indexer, driver=driver))

        # TODO hmm so this bit is actually super fast, takes like 1.5 secs
        # need to speed up the preparation
        driver.get(url)
        assert not helper.sidebar.visible
        confirm("grey icon. sidebar shouldn't be visible")

        driver.get(tutorial)
        assert not helper.sidebar.visible
        confirm("green icon. sidebar shouldn't be visible")

        # TODO ideally we'll get rid of it
        # at the moment without this sleep chrome pretty much always fails
        def sleep_if_chrome() -> None:
            if driver.name == 'chrome':
                sleep(0.01)

        # switch between these in quick succession deliberately
        # previously it was triggering a bug when multiple sidebars would be injected due to race condition
        for i in range(100):
            driver.get(url)
            sleep_if_chrome()
            driver.get(tutorial)
            sleep_if_chrome()
            if i % 10 == 0:
                # huh, it's quite slow... to run it on single iteration
                # what it's really testing here is that there is only one promnesia frame/sidebar
                assert not helper.sidebar.visible

        # hmm, headless chrome web test failed here on CI once...
        # yep, still happening...
        # and firefox is failing as well at times (which is sort of good news)
        helper.sidebar.open()
        confirm("green icon. sidebar should open and show one visit")

        driver.back()
        assert not helper.sidebar.visible
        confirm("grey/purple icon, sidebar shouldn't be visible")

        # again, stress test it to try to trigger weird bugs
        for i in range(100):
            sleep_if_chrome()
            driver.forward()

            # TODO ugh. still failing here sometimes under headless firefox??
            # if i % 10 == 0:
            #     assert helper.sidebar.visible

            sleep_if_chrome()
            driver.back()
            if i % 10 == 0:
                # huh, it's quite slow... to run it on single iteration
                # what it's really testing here is that there is only one promnesia frame/sidebar
                assert not helper.sidebar.visible

        # checks it's still possible to interact with the sidebar
        assert not helper.sidebar.visible

        driver.forward()

        # sidebar should be preserved between page transitions
        assert helper.sidebar.visible
        confirm('green icon, sidebar visible')

        # check that still can interact with the sidebar
        helper.sidebar.close()
        confirm('green icon, sidebar is closed')


@browsers()
def test_unreachable(tmp_path: Path, browser: Browser) -> None:
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
def test_stress(tmp_path: Path, browser: Browser) -> None:
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
def test_fuzz(tmp_path: Path, browser: Browser) -> None:
    # TODO ugh. this still results in 'tab permissions' pages, but perhaps because of closed tabs?
    # dunno if it's worth fixing..
    urls = {
        'https://www.iana.org/domains/reserved': 'IANA',
        'iana.org/domains/reserved': 'IANA2',
    }
    with _test_helper(
            tmp_path,
            index_urls(urls),
            'https://example.com',
            browser=browser,
            notify_contexts=True,
    ) as helper:
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
                send_key('Ctrl+Shift+t')  # restore tabs
                sleep(0.1)
        trigger_callback(driver, cb)
        confirm("shouldn't result in 'unexpected error occured'; show only show single notification per page")


@browsers()
def test_duplicate_background_pages(tmp_path: Path, driver: Driver) -> None:
    url = 'https://example.com'
    indexer = index_urls({'whatever.coom': '123'})
    with run_server(tmp_path=tmp_path, indexer=indexer, driver=driver) as helper:
        driver.get(url)

        helper._sidebar.open()
        confirm('sidebar opened?')

        original = driver.current_window_handle

        # NOTE: Sidebar.trigger_search asserts that only one search window is opened
        # so this test is actually fairly automated
        helper._sidebar.trigger_search()
        driver.switch_to.window(original)

        helper._sidebar.trigger_search()
        driver.switch_to.window(original)

        confirm('only two search pages should be opened (in background tabs)')

        helper._sidebar.close()
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


@browsers()
def test_multiple_page_updates(tmp_path: Path, driver: Driver) -> None:
    # on some pages, onUpdated is triggered multiple times (because of iframes or perhaps something else??)
    # which previously resulted in flickering sidebar/performance degradation etc, so it's a regression test against this
    # TODO would be nice to hook to the backend and check how many requests it had...
    url = 'https://github.com/karlicoss/promnesia/projects/1'
    indexer = index_urls([
        ('https://github.com/karlicoss/promnesia', 'some comment'),
        ('https://github.com/karlicoss/promnesia/projects/1', 'just a note for the sidebar'),
    ])
    with run_server(tmp_path=tmp_path, indexer=indexer, driver=driver, notify_contexts=True, show_dots=True) as helper:
        driver.get(url)

        had_toast = False
        # TODO need a better way to check this...
        for _ in range(50):
            toasts = driver.find_elements(By.CLASS_NAME, 'toastify')
            if len(toasts) == 1:
                had_toast = True
            assert len(toasts) <= 1
            sleep(0.1)
        assert had_toast

        helper._sidebar.open()
        helper._sidebar.close()

        xpath = '//a[@href = "https://github.com/karlicoss/promnesia"]'
        links_to_mark = driver.find_elements(By.XPATH, xpath)
        assert len(links_to_mark) > 2  # sanity check
        for l in links_to_mark:
            assert 'promnesia-visited' in l.get_attribute('class')
            # TODO would be nice to test clicking on them...

        # meh...
        header_link = driver.find_elements(By.XPATH, '//a[text() = "promnesia" and @href = "/karlicoss/promnesia"]')[0]
        # hmm a bit crap, but works!!
        header_link.find_element(By.XPATH, './../..').find_element(By.CLASS_NAME, 'promnesia-visited-toggler').click()

        popup = driver.find_element(By.CLASS_NAME, 'context')
        assert popup.text == 'some comment'

        assert is_visible(driver, popup)


# TODO FIXME need to test racey conditions _while_ page is loading, results in this 'unexpected error occured'?


# TODO shit, sometimes I have 'bindSidebarData is not defined'? with vebose errors on demo_how_did_i_get_here
