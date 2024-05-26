#!/usr/bin/env python3
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from time import sleep
from typing import Iterator, TypeVar, Callable

import pytest

if __name__ == '__main__':
    # TODO ugh need to figure out PATH
    # python3 -m pytest -s tests/server_test.py::test_query
    pytest.main(['-s', __file__])


from selenium.webdriver import Remote as Driver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait as Wait
from selenium.webdriver.support import expected_conditions as EC

from promnesia.tests.utils import index_urls
from promnesia.tests.server_helper import run_server as wserver
from promnesia.logging import LazyLogger

from common import under_ci, has_x, local_http_server, notnone
from webdriver_utils import is_visible, wait_for_alert, get_webdriver
from addon import get_addon_source, Addon, LOCALHOST, addon


logger = LazyLogger('promnesia-tests', level='debug')


@dataclass
class Browser:
    dist: str
    headless: bool

    @property
    def name(self) -> str:
        return self.dist.split('-')[0]  # TODO meh

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


def confirm(what: str) -> None:
    is_headless = 'headless' in os.environ.get('PYTEST_CURRENT_TEST', '')
    if is_headless:
        # ugh.hacky
        Headless().confirm(what)
        return

    import click
    click.confirm(click.style(what, blink=True, fg='yellow'), abort=True)
    # TODO focus window if not headless


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
def driver(tmp_path: Path, browser: Browser) -> Iterator[Driver]:
    profile_dir = tmp_path / 'browser_profile'
    res = get_webdriver(
        profile_dir=profile_dir,
        addon_source=get_addon_source(kind=browser.dist),
        browser=browser.name,
        headless=browser.headless,
        logger=logger,
    )
    try:
        yield res
    finally:
        res.quit()


@dataclass
class Backend:
    # directory with database and configs
    backend_dir: Path


@pytest.fixture
def backend(tmp_path: Path, addon: Addon) -> Iterator[Backend]:
    backend_dir = tmp_path
    # TODO ideally should index in a separate thread? and perhaps start server too
    with wserver(db=backend_dir / 'promnesia.sqlite') as srv:
        # this bit (up to yield) takes about 1.5s -- I guess it's the 1s sleep in configure_extension
        addon.configure(host=LOCALHOST, port=srv.port)
        addon.helper.driver.get('about:blank')  # not sure if necessary
        yield Backend(backend_dir=backend_dir)


@browsers()
def test_installs(addon: Addon) -> None:
    """
    Even loading the extension into webdriver is pretty elaborate, so the test just checks it works
    """
    assert addon.helper.addon_id is not None


@browsers()
def test_settings(addon: Addon, driver: Driver) -> None:
    """
    Just a basic test for opening options page and making sure it loads options
    """
    addon.options_page.open()
    hh = driver.find_element(By.ID, 'host_id')
    assert hh.get_attribute('value') == 'http://localhost:13131'  # default

    addon.configure(host=LOCALHOST, port='12345', show_dots=False)
    driver.get('about:blank')

    addon.options_page.open()
    hh = driver.find_element(By.ID, 'host_id')
    assert hh.get_attribute('value') == 'http://localhost:12345'


@browsers()
def test_backend_status(addon: Addon, driver: Driver) -> None:
    """
    We should get an alert if backend is unavailable on the status check
    """
    addon.options_page.open()
    addon.options_page._set_endpoint(host='https://nosuchhost.com', port='1234')

    driver.find_element(By.ID, 'backend_status_id').click()

    alert = wait_for_alert(driver)
    assert 'ERROR' in alert.text
    alert.accept()

    # TODO implement positive check, e.g. when backend is present


@browsers()
def test_sidebar_position(addon: Addon, driver: Driver) -> None:
    """
    Checks that default sidebar position is on the right, and that changing it to --bottom: 1 works
    """
    options_page = addon.options_page
    options_page.open()
    # TODO WTF; if we don't open extension page once, we can't read out hotkeys from the chrome extension settings file
    # (so e.g. trigger_command isn't working???)
    options_page._set_endpoint(host=None, port=None)  # we don't need backend here

    driver.get('https://example.com')

    addon.sidebar.open()
    confirm("sidebar: should be displayed on the right (default)")
    addon.sidebar.close()

    options_page.open()
    settings = """
#promnesia-frame {
  --bottom: 1;
  --size: 20%;
}""".strip()
    options_page._set_position(settings)
    options_page._save()

    driver.get('https://example.com')
    addon.sidebar.open()
    confirm("sidebar: should be displayed below")


@browsers()
def test_blacklist_custom(addon: Addon, driver: Driver) -> None:
    addon.configure(port='12345', blacklist=('stackoverflow.com',))
    driver.get('https://stackoverflow.com/questions/27215462')

    addon.activate()
    manual.confirm('page should be blacklisted (black icon), you should see an error notification')
    # make sure there is not even the frame for blacklisted page
    assert not addon.sidebar.available

    # reset blacklist
    # also running without backend here, so need to set host to none as well
    addon.configure(host=None, blacklist=())
    driver.back()
    driver.refresh()

    addon.sidebar.open()
    manual.confirm('sidebar: should be visible')


@browsers()
def test_blacklist_builtin(addon: Addon, driver: Driver) -> None:
    addon.configure(port='12345')
    driver.get('https://www.hsbc.co.uk/mortgages/')

    addon.activate()
    manual.confirm('page should be blacklisted (black icon), your should see an error notification')
    # make sure there is not even the frame for blacklisted page
    assert not addon.sidebar.available

    # reset blacklist
    # also running without backend here, so need to set host to none as well
    addon.configure(host=None, excludelists=())
    driver.back()
    driver.refresh()

    addon.sidebar.open()
    manual.confirm('sidebar: should be visible')


@browsers(FF, CH)
def test_add_to_blacklist_context_menu(addon: Addon, driver: Driver) -> None:
    # doesn't work on headless because not sure how to interact with context menu.
    addon.configure(port='12345')
    driver.get('https://example.com')

    addon.open_context_menu()
    addon.helper.gui_write(['enter'])  # select first item

    confirm('shows prompt with alert to enter pattern to block?')
    wait_for_alert(driver).accept()
    # ugh, seems necessary to guard with sleep; otherwise racey
    sleep(0.5)

    driver.get(driver.current_url)
    confirm('page should be blacklisted (black icon)')


# todo might be nice to run soft asserts for this test?
@browsers()
def test_visits(addon: Addon, driver: Driver, backend: Backend) -> None:
    from promnesia.tests.sources.test_hypothesis import index_hypothesis

    test_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    # test_url = "file:///usr/share/doc/python3/html/library/contextlib.html" # todo ??

    index_hypothesis(backend.backend_dir)

    driver.get(test_url)
    confirm("sidebar: shouldn't be visible")

    with addon.sidebar.ctx():
        # hmm not sure how come it returns anything at all.. but whatever
        srcs = driver.find_elements(By.CLASS_NAME, 'src')
        for s in srcs:
            # elements should be bound to the sidebar, but aren't displayed yet
            assert not is_visible(driver, s), s
        assert len(srcs) >= 8, srcs
        # todo ugh, need to filter out filters, how to only query the ones in the sidebar?

    addon.sidebar.open()
    confirm('sidebar: you should see hypothesis contexts')

    with addon.sidebar.ctx():
        # sleep(1)
        link = driver.find_element(By.PARTIAL_LINK_TEXT, 'how_algorithms_shape_our_world')
        assert is_visible(driver, link), link

        contexts = driver.find_elements(By.CLASS_NAME, 'context')
        for c in contexts:
            assert is_visible(driver, c), c
        assert len(contexts) == 8

    addon.sidebar.close()
    confirm("sidebar: shouldn't be visible")


@browsers()
def test_search_around(addon: Addon, driver: Driver, backend: Backend) -> None:
    from promnesia.tests.sources.test_hypothesis import index_hypothesis

    # TODO hmm. dunno if we want to highlight only result with the same timestamp, or the results that are 'near'??
    ts = int(datetime.strptime("2017-05-22T10:59:12.082375+00:00", '%Y-%m-%dT%H:%M:%S.%f%z').timestamp())

    index_hypothesis(backend.backend_dir)

    addon.open_search_page(f'?utc_timestamp_s={ts}')

    visits = driver.find_element(By.ID, 'visits')
    sleep(1)  # wait till server responds and renders results
    results = visits.find_elements(By.CSS_SELECTOR, 'li')
    assert len(results) == 9

    hl = visits.find_element(By.CLASS_NAME, 'highlight')
    assert 'anthrocidal' in hl.text

    manual.confirm('you should see search results, "anthrocidal" should be highlighted red')
    # FIXME test clicking search around in actual search page.. it didn't work, seemingly because of initBackground() handling??


@browsers()
def test_show_visited_marks(addon: Addon, driver: Driver, backend: Backend) -> None:
    # fmt: off
    visited = {
        'https://en.wikipedia.org/wiki/Special_linear_group': 'some note about linear groups',
        'http://en.wikipedia.org/wiki/Unitary_group'        : None,
        'en.wikipedia.org/wiki/Transpose'                   : None,
    }
    # fmt: on
    test_url = "https://en.wikipedia.org/wiki/Symplectic_group"

    index_urls(visited)(backend.backend_dir)

    addon.configure(show_dots=False)

    driver.get(test_url)

    sleep(2)  # hmm not sure why it's necessary, but often fails headless firefox otherwise
    addon.mark_visited()
    sleep(1)  # marks are async, wait till it marks

    slg = driver.find_elements(By.XPATH, '//a[contains(@href, "/wiki/Special_linear_group")]')
    assert len(slg) > 0
    for s in slg:
        assert 'promnesia-visited' in notnone(s.get_attribute('class'))

    confirm(
        "You should see visited marks near 'Special linear group', 'Unitary group', 'Transpose'. 'Special linear group' should be green."
    )


@browsers()
@pytest.mark.parametrize(
    'url',
    [
        "https://en.wikipedia.org/wiki/Symplectic_group",

        # regression test for https://github.com/karlicoss/promnesia/issues/295
        # note: seemed to reproduce on chrome more consistently for some reason
        "https://www.udemy.com/course/javascript-bible/",
    ],
    ids=['wiki', 'udemy'],
)
def test_sidebar_basic(url: str, addon: Addon, driver: Driver, backend: Backend) -> None:
    if 'udemy' in url:
        pytest.skip('TODO udemy tests are very timing out. Perhaps because of cloudflare protection?')

    visited = {
        # this also tests org-mode style link highlighting (custom anchorme version)
        url: 'whatever\nalso [[https://wiki.openhumans.org/wiki/Personal_Science_Wiki][Personal Science Wiki]]\nmore text',
    }
    src = "ælso test unicode 💩"

    addon.configure(show_dots=True)

    index_urls(visited, source_name=src)(backend.backend_dir)

    driver.get(url)

    addon.sidebar.open()

    # a bit crap, but also annoying to indent just to put it in context considering it impacts all of the test...
    # ugh also it doesn't work for some reason..
    # helper._sidebar.ctx().__enter__()

    with addon.sidebar.ctx():
        filters = addon.sidebar.filters
        assert len(filters) == 2, filters

        _all = filters[0]
        tag  = filters[1]

        # this should happen in JS
        sanitized = src.replace(' ', '')

        assert 'all'     in _all.text
        assert sanitized in tag.text

        assert 'all'     in notnone(_all.get_attribute('class')).split()
        assert sanitized in notnone(tag .get_attribute('class')).split()

        visits = addon.sidebar.visits
        assert len(visits) == 1, visits
        [v] = visits

        assert v.find_element(By.CLASS_NAME, 'src').text == sanitized
        ctx_el = v.find_element(By.CLASS_NAME, 'context')
        assert ctx_el.text == visited[url]
        # make sure linkifying works
        assert ctx_el.find_element(By.TAG_NAME, 'a').get_attribute('href') == 'https://wiki.openhumans.org/wiki/Personal_Science_Wiki'

    confirm("You should see green icon, also one visit in sidebar. Make sure the unicode is displayed correctly.")


@browsers()
def test_search_command(addon: Addon, driver: Driver, backend: Backend) -> None:
    """
    Basic test that search command handler works and it opens search inteface
    """
    from promnesia.tests.sources.test_hypothesis import index_hypothesis

    index_hypothesis(backend.backend_dir)

    test_url = "https://en.wikipedia.org/wiki/Symplectic_vector_space"
    driver.get(test_url)

    addon.search()
    # TODO actually search something?
    # TODO use current domain as default? or 'parent' url?
    confirm("You shoud see search prompt now, with focus on search field")


@browsers()
def test_new_background_tab(addon: Addon, driver: Driver, backend: Backend) -> None:
    from promnesia.tests.sources.test_hypothesis import index_hypothesis

    index_hypothesis(backend.backend_dir)

    addon.configure(notify_contexts=True)

    start_url = "http://www.e-flux.com/journal/53/59883/the-black-stack/"
    # bg_url_text = "El Proceso (The Process)"
    # TODO generate some fake data instead?
    driver.get(start_url)
    manual.confirm('you should see notification about contexts')
    page_logo = driver.find_element(By.XPATH, '//a[@class="page-logo"]')
    page_logo.send_keys(Keys.CONTROL + Keys.ENTER)  # ctrl+click -- opens the link in new background tab
    manual.confirm('you should not see any new notifications')
    # TODO switch to new tab?
    # TODO https://www.e-flux.com/journal/53/


PYTHON_DOC_PATH = Path('/usr/share/doc/python3/html')


@pytest.fixture
def exit_stack() -> Iterator[ExitStack]:
    with ExitStack() as stack:
        yield stack


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
def test_sidebar_navigation(base_url: str, addon: Addon, driver: Driver, backend: Backend, exit_stack: ExitStack) -> None:
    if 'file:' in base_url and driver.name == 'chrome':
        pytest.skip("TODO used to work, but must have broken after some Chrome update?")
        # seems broken on any local page -- only transparent sidebar frame is shown
        # the issue is that contentDocument.body is null -- no idea why

    if driver.name == 'chrome':
        pytest.skip(
            "TODO need to split the test into version which isn's using back/forward. see https://bugs.chromium.org/p/chromedriver/issues/detail?id=4329"
        )
        # also need to extract a scenario for manual testing I guess

    if base_url == 'LOCAL':
        local_addr = exit_stack.enter_context(local_http_server(PYTHON_DOC_PATH, port=15454))
        base_url = local_addr

    tutorial = f'{base_url}/tutorial/index.html'
    reference = f'{base_url}/reference/index.html'
    # reference has a link to tutorial (so will display a context)

    urls = {
        tutorial: 'TODO read this https://please-highligh-this-link.com',
        reference: None,
    }
    index_urls(urls)(backend.backend_dir)

    url = reference

    # TODO hmm so this bit is actually super fast, takes like 1.5 secs
    # need to speed up the preparation
    driver.get(url)
    assert not addon.sidebar.visible
    confirm("grey icon. sidebar should NOT be visible")

    driver.get(tutorial)
    assert not addon.sidebar.visible
    confirm("green icon. sidebar should NOT be visible")

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
            assert not addon.sidebar.visible

    # hmm, headless chrome web test failed here on CI once...
    # yep, still happening...
    # and firefox is failing as well at times (which is sort of good news)
    addon.sidebar.open()
    confirm("green icon. sidebar should open and show one visit")

    driver.back()
    assert not addon.sidebar.visible
    confirm("grey/purple icon, sidebar should NOT be visible")

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
            assert not addon.sidebar.visible

    # checks it's still possible to interact with the sidebar
    assert not addon.sidebar.visible

    driver.forward()

    # sidebar should be preserved between page transitions
    assert addon.sidebar.visible
    confirm('green icon, sidebar visible')

    # check that still can interact with the sidebar
    addon.sidebar.close()
    confirm('green icon, sidebar is closed')


@browsers()
def test_unreachable(addon: Addon, driver: Driver, backend: Backend) -> None:
    pytest.skip("NOTE: broken at the moment because webNavigation.onCompleted isn't working for unreachable pages")

    url = 'https://somenonexist1ngurl.com'
    urls = {
        url: 'some context',
    }

    index_urls(urls)(backend.backend_dir)

    addon.configure(notify_contexts=True, verbose_errors=True)

    try:
        driver.get(url)
    except:
        # results in exception because it's unreachable
        pass
    manual.confirm('green icon, no errors, desktop notification with contexts')


@browsers()
def test_stress(addon: Addon, driver: Driver, backend: Backend) -> None:
    url = 'https://www.reddit.com/'
    urls = [(f'{url}/subpath/{i}.html', f'context {i}' if i > 10000 else None) for i in range(50000)]

    index_urls(urls)(backend.backend_dir)

    driver.get(url)
    addon.activate()

    # todo I guess it's kinda tricky to test in headless webdriver
    manual.confirm(
        '''
Is performance reasonable?
The sidebar should show up, and update gradually.
You should be able to scroll the page, trigger tooltips, etc., without any lags.
'''.strip()
    )


@browsers()
def test_fuzz(addon: Addon, driver: Driver, backend: Backend) -> None:
    # TODO ugh. this still results in 'tab permissions' pages, but perhaps because of closed tabs?
    # dunno if it's worth fixing..
    urls = {
        'https://www.iana.org/help/example-domains': 'IANA',
        'iana.org/help/example-domains': 'IANA2',
    }
    index_urls(urls)(backend.backend_dir)

    addon.configure(notify_contexts=True)

    driver.get('https://example.com')
    tabs = 30
    for _ in range(tabs):
        # find and click "More information" link, open them in new background tabs
        driver.find_element(By.TAG_NAME, 'a').send_keys(Keys.CONTROL + Keys.RETURN)

    sleep(5)
    for _ in range(tabs - 2):
        driver.close()
        sleep(0.1)
        driver.switch_to.window(driver.window_handles[0])

    if addon.helper.headless:
        pytest.skip("Rest of this test uses send_key to restore tab and it's not working under headless webdriver :(")

    for _ in range(10):
        addon.helper.gui_hotkey('Ctrl+Shift+t')  # restore tabs
        sleep(0.1)
    confirm("shouldn't result in 'unexpected error occured'; show only show single notification per page")


@browsers()
def test_duplicate_background_pages(addon: Addon, driver: Driver, backend: Backend) -> None:
    url = 'https://example.com'
    index_urls({'whatever.coom': '123'})(backend.backend_dir)

    driver.get(url)

    addon.sidebar.open()
    confirm('sidebar opened?')

    original = driver.current_window_handle

    # NOTE: Sidebar.trigger_search asserts that only one search window is opened
    # so this test is actually fairly automated
    addon.sidebar.trigger_search()
    driver.switch_to.window(original)

    addon.sidebar.trigger_search()
    driver.switch_to.window(original)

    confirm('only two search pages should be opened (in background tabs)')

    addon.sidebar.close()
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
def test_showvisits_popup(addon: Addon, driver: Driver, backend: Backend) -> None:
    url = 'https://www.iana.org/'
    indexer = index_urls([('https://www.iana.org/abuse', 'some comment')])
    indexer(backend.backend_dir)

    addon.configure(notify_contexts=True, show_dots=True)

    driver.get(url)
    # todo might need to wait until marks are shown?
    link_with_popup = driver.find_elements(By.XPATH, '//a[@href = "/abuse"]')[0]

    # wait till visited marks appear
    Wait(driver, timeout=5).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'promnesia-visited')),
    )
    addon.move_to(link_with_popup)  # hover over visited mark
    # meh, but might need some time to render..
    popup = Wait(driver, timeout=5).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'context')),
    )
    sleep(3)  #  text might take some time to render too..
    assert popup.text == 'some comment'

    assert is_visible(driver, popup)


@browsers()
def test_multiple_page_updates(addon: Addon, driver: Driver, backend: Backend) -> None:
    # on some pages, onUpdated is triggered multiple times (because of iframes or perhaps something else??)
    # which previously resulted in flickering sidebar/performance degradation etc, so it's a regression test against this
    # TODO would be nice to hook to the backend and check how many requests it had...
    url = 'https://github.com/karlicoss/promnesia/projects/1'
    indexer = index_urls(
        [
            ('https://github.com/karlicoss/promnesia', 'some comment'),
            ('https://github.com/karlicoss/promnesia/projects/1', 'just a note for the sidebar'),
        ]
    )
    indexer(backend.backend_dir)

    addon.configure(notify_contexts=True, show_dots=True)

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

    addon.sidebar.open()
    addon.sidebar.close()

    xpath = '//a[@href = "/karlicoss/promnesia"]'
    links_to_mark = driver.find_elements(By.XPATH, xpath)
    assert len(links_to_mark) > 2  # sanity check
    for l in links_to_mark:
        assert 'promnesia-visited' in notnone(l.get_attribute('class'))
        # TODO would be nice to test clicking on them...


# TODO FIXME need to test racey conditions _while_ page is loading, results in this 'unexpected error occured'?


# TODO shit, sometimes I have 'bindSidebarData is not defined'? with vebose errors on demo_how_did_i_get_here
