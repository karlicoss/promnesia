import os
import shlex
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat
from time import sleep
from typing import Literal

import click
import psutil
import pytest
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver import Remote as Driver
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.remote.webelement import WebElement

from .common import logger
from .utils import has_x

# useful for debugging
# from selenium.webdriver.remote.remote_connection import LOGGER
# from selenium.webdriver.common.driver_finder import logger as driver_finder_logger
# from selenium.webdriver.common.selenium_manager import logger as selenium_manager_logger
# from promnesia.logging import setup_logger
# for logger_ in [LOGGER, driver_finder_logger, selenium_manager_logger]:
#     # ugh.. these loggers have no handlers by default?
#     # so just .setLevel doesn't work...
#     setup_logger(logger=logger_, level='DEBUG')


@dataclass
class Browser:
    name: Literal['chrome', 'firefox']
    headless: bool


# fmt: off
FIREFOX          = Browser('firefox', headless=False)
CHROME           = Browser('chrome' , headless=False)
FIREFOX_HEADLESS = Browser('firefox', headless=True)
CHROME_HEADLESS  = Browser('chrome' , headless=True)
# fmt: on
# TODO ugh, I guess it's not that easy to make it work because of isAndroid checks...
# I guess easy way to test if you really want is to temporary force isAndroid to return true in extension...
# FIXME bring it back later?
# FM = Browser('firefox-mobile', headless=False)


def browsers(*br: Browser):
    if len(br) == 0:
        # if no args passed, test all combinations
        br = (
            CHROME,
            FIREFOX,
            CHROME_HEADLESS,
            FIREFOX_HEADLESS,
        )  # fmt: skip
    if not has_x():
        # this is convenient to filter out automatically for CI
        br = tuple(b for b in br if b.headless)
    return pytest.mark.parametrize(
        "browser",
        br,
        ids=[f'browser={b.name}_{"headless" if b.headless else "gui"}' for b in br],
    )


def get_current_frame(driver: Driver) -> WebElement | None:
    # idk why is it so hard to get current frame in selenium, but it is what it is
    # https://github.com/seleniumhq/selenium-google-code-issue-archive/issues/4305#issuecomment-192026569
    # NOTE: that may not always work inside iframes?
    # e.g. see this https://bugs.chromium.org/p/chromedriver/issues/detail?id=4440
    #  , chromedriver had this behaviour broken at some point
    return driver.execute_script('return window.frameElement')


@contextmanager
def frame_context(driver: Driver, *, frame: WebElement) -> Iterator[WebElement]:
    current = get_current_frame(driver)
    assert current is None, current  # just in case? not sure if really necessary
    # todo use switching to parent instead??
    driver.switch_to.frame(frame)
    try:
        yield frame
    finally:
        # hmm mypy says it can't be None
        # but pretty sure it worked when current frame is None?
        # see https://github.com/SeleniumHQ/selenium/blob/trunk/py/selenium/webdriver/remote/switch_to.py
        driver.switch_to.frame(current)  # type: ignore[arg-type]


@contextmanager
def window_context(driver: Driver, window_handle: str) -> Iterator[None]:
    original = driver.current_window_handle
    driver.switch_to.window(window_handle)
    try:
        yield
    finally:
        driver.switch_to.window(original)


def is_visible(driver: Driver, element: WebElement) -> bool:
    # apparently is_display checks if element is on the page, not necessarily within viewport??
    # but I also found  element.is_displayed() to be unreliable in other direction too
    # (returning true for elements that aren't displayed)
    # it seems to even differ between browsers
    return driver.execute_script('return arguments[0].checkVisibility()', element)


def is_headless(driver: Driver) -> bool:
    if driver.name == 'firefox':
        return driver.capabilities.get('moz:headless', False)
    elif driver.name == 'chrome':
        return any('--headless' in c for c in get_browser_process(driver).cmdline())
        # ugh.. looks like this stopped working?
        # https://antoinevastel.com/bot%20detection/2018/01/17/detect-chrome-headless-v2.html
        # return driver.execute_script("return navigator.webdriver") is True
    else:
        raise RuntimeError(driver.name)


def wait_for_alert(driver: Driver) -> Alert:
    """
    Alert is often shown as a result of async operations, so this is to prevent race conditions
    """
    e: Exception | None = None
    for _ in range(100 * 10):  # wait 10 secs max
        try:
            return driver.switch_to.alert
        except NoAlertPresentException as ex:
            e = ex
            sleep(0.01)
            continue
    assert e is not None
    raise e


def get_webdriver(
    *,
    profile_dir: Path,
    addon_source: Path,
    browser: str,
    headless: bool,
    logger,
) -> Driver:
    # hmm. seems like if it can't find the driver, selenium automatically downloads it?
    driver: Driver
    version_data: dict[str, str] = {}
    if browser == 'firefox':
        ff_options = webdriver.FirefoxOptions()

        ## you can adjust this to change logging level of geckodriver (e.g. "info"/"trace")
        # see https://firefox-source-docs.mozilla.org/testing/geckodriver/TraceLogs.html
        geckodriver_log_level: str | None = "warn"  # None means default which is "info"
        if geckodriver_log_level is not None:
            ff_options.log.level = geckodriver_log_level  # type: ignore[assignment]  # ?? seems like mypy is confused

        ff_options.set_preference('profile', str(profile_dir))

        # selenium manager should download latest dev version of firefox
        ff_options.browser_version = 'dev'

        # Without this, notifications aren't showing in firefox
        # I think possibly it's because we run under tox, and maybe it needs to connect to some bus or something
        ff_options.set_preference("alerts.useSystemBackend", value=False)

        # ff_options.binary_location = ''  # set custom path here
        # e.g. use firefox from here to test https://www.mozilla.org/en-GB/firefox/developer/
        if headless:
            ff_options.add_argument('--headless')

            # In theory that should allow to start a remote debuggger? The port is visible in ss -tulpen.
            # However I can't manage to connect to it using either firefox or chrome devtools, not sure why..
            # ff_options.set_preference("devtools.debugger.remote-enabled", True)
            # ff_options.set_preference("devtools.chrome.enabled", True)
            # ff_options.add_argument('--start-debugger-server=9222')

        driver = webdriver.Firefox(
            options=ff_options,
            # 2 means stderr (seems like otherwise it's not logging at all)
            service=webdriver.FirefoxService(log_output=2),
        )

        addon_id = driver.install_addon(str(addon_source), temporary=True)
        logger.debug(f'firefox addon id: {addon_id}')

        # TODO 'binary'? might not be present?
        for key in ['moz:geckodriverVersion', 'moz:headless', 'moz:profile']:
            version_data[key] = driver.capabilities[key]
    elif browser == 'chrome':
        cr_options = webdriver.ChromeOptions()

        # in case user wants some adhoc override
        chrome_bin: str | None = None  # default (e.g. apt version)

        # NOTE: regular/stable chrome, --load-extension isn't working anymore
        # https://stackoverflow.com/questions/25064523/load-extension-parameter-for-chrome-doesnt-work

        if chrome_bin is not None:
            cr_options.binary_location = chrome_bin
        else:
            # selenium manager should download latest "chrome for testing"
            # available versions seem to be here: https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json
            cr_options.browser_version = 'dev'

            # seems like necessary from chrome-for-testing? otherwise doesn't start
            cr_options.add_argument('--no-sandbox')

        cr_options.add_argument(f'--load-extension={addon_source}')
        cr_options.add_argument(f'--user-data-dir={profile_dir}')  # todo point to a subdir?

        if headless:
            if Path('/.dockerenv').exists():
                # necessary, otherwise chrome fails to start under containers
                cr_options.add_argument('--no-sandbox')

            # regular --headless doesn't support extensions for some reason
            cr_options.add_argument('--headless=new')

        # not sure this does anything??
        cr_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})

        # ugh. this is necessary for chrome to consider extension pages as part of normal tabs
        # https://github.com/SeleniumHQ/selenium/issues/15685
        # https://issues.chromium.org/issues/416666972
        # https://issues.chromium.org/issues/409441960
        cr_options.add_experimental_option('enableExtensionTargets', value=True)

        # generally 'selenium manager' downloads the correct driver version itself
        chromedriver_bin: str | None = None  # default

        # 2 means stderr (seems like otherwise it's not logging at all)
        service = webdriver.ChromeService(executable_path=chromedriver_bin, log_output=2)
        driver = webdriver.Chrome(service=service, options=cr_options)

        version_data['chromedriverVersion'] = driver.capabilities['chrome']['chromedriverVersion']
        version_data['userDataDir'] = driver.capabilities['chrome']['userDataDir']
    else:
        raise RuntimeError(f'Unexpected browser {browser}')

    for key in ['browserName', 'browserVersion']:
        version_data[key] = driver.capabilities[key]

    # ugh, seems like this is the only way to get the browser binary path?
    # seems like webdriver never stores it anywhere, it just passed directly to chromedriver/geckodriver processes or something?
    version_data['browser_cmdline'] = shlex.join(get_browser_process(driver).cmdline())
    version_data['driver_path'] = getattr(driver.service, '_path')

    logger.info(f'browser/driver info:\n{pformat(version_data)}')

    # Ugh. Tried a bunch of things to print webdriver version stuff during all tests (not just failed ones), but it's kind of annoying.
    # - sys.__stdout__/__stderr__/os.write don't work
    # - with capsys.disabled() works, but then it breakes lines between test names and results.. which is a bit annoying
    # - pytest_terminal_summary in conftest could work, but it only prints at the end (and doesn't work with parallel tests)
    # - doesn't look like there is a way to extract this version in advance from selenium manager??
    #   overall it looks a bit too defenside... e.g. --offline mode can return wrong version instead of erroring
    # Probably the best thing would be to just enable -s option on CI?
    return driver


def get_browser_process(driver: webdriver.Remote) -> psutil.Process:
    driver_pid = driver.service.process.pid  # type: ignore[attr-defined]
    dprocess = psutil.Process(driver_pid)
    [process] = dprocess.children()
    cmdline = process.cmdline()
    if driver.name == 'firefox':
        assert '--marionette' in cmdline, cmdline
    elif driver.name == 'chrome':
        assert '--enable-automation' in cmdline, cmdline
    else:
        raise AssertionError
    return process


@pytest.fixture
def driver(*, tmp_path: Path, addon_source: Path, browser: Browser) -> Iterator[Driver]:
    profile_dir = tmp_path / 'browser_profile'
    with get_webdriver(
        profile_dir=profile_dir,
        addon_source=addon_source,
        browser=browser.name,
        headless=browser.headless,
        logger=logger,
    ) as res:
        try:
            yield res
        finally:
            # ugh. in firefox get_webdriver we set log_output=2 (stderr) to see driver logs
            # however seems like webdriver will try to close it which may result in crashes on shutdown
            # https://github.com/SeleniumHQ/selenium/blob/4c64df2cde912aec7000589b2dc96fd21c6c27cd/py/selenium/webdriver/common/service.py#L146-L152
            service = res.service  # type: ignore[attr-defined] # ty: ignore[unresolved-attribute]
            if service.log_output == 2:
                service.log_output = None


@dataclass
class Manual:
    '''
    Helper for tests that are not yet fully automated and require a human to check...
    By default:
    - if running in headless mode, will automatically assume 'yes'
    - if running with GUI, will prompt user for confirmation
    '''

    mode: Literal['auto', 'headless', 'interactive'] = 'auto'

    def confirm(self, what: str) -> None:
        is_headless = 'headless' in os.environ.get('PYTEST_CURRENT_TEST', '')

        mode = self.mode
        if mode == 'auto':
            if is_headless:
                mode = 'headless'
            else:
                mode = 'interactive'

        if mode == 'headless':
            click.echo(click.style(what, fg='yellow'), nl=False)
            click.echo(click.style(' -- headless mode, responding "yes"', fg='green'))
        elif mode == 'interactive':
            click.confirm(click.style(what, fg='yellow', blink=True), abort=True)
            # TODO focus window if not headless
        else:
            raise RuntimeError(f"Shouldn't happen: mode={mode}")
