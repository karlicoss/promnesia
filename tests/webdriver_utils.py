from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Literal

import psutil
import pytest
from loguru import logger
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver import Remote as Driver
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.remote.webelement import WebElement


@dataclass
class Browser:
    name: Literal['chrome', 'firefox']
    headless: bool


def get_current_frame(driver: Driver) -> WebElement | None:
    # idk why is it so hard to get current frame in selenium, but it is what it is
    # https://github.com/seleniumhq/selenium-google-code-issue-archive/issues/4305#issuecomment-192026569
    return driver.execute_script('return window.frameElement')


@contextmanager
def frame_context(driver: Driver, frame) -> Iterator[WebElement | None]:
    # todo return the frame maybe?
    current = get_current_frame(driver)
    driver.switch_to.frame(frame)
    try:
        new_frame = get_current_frame(driver)
        yield new_frame
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
    # useful for debugging
    # import logging
    # from selenium.webdriver.remote.remote_connection import LOGGER
    # LOGGER.setLevel(logging.DEBUG)

    # hmm. seems like if it can't find the driver, selenium automatically downloads it?
    driver: Driver
    version_data: dict[str, str]
    if browser == 'firefox':
        ff_options = webdriver.FirefoxOptions()
        ff_options.set_preference('profile', str(profile_dir))

        # TODO enable it back? for now relying on docker provided version on github actions
        # selenium manager should download latest dev version of firefox
        # ff_options.browser_version = 'dev'

        # Without this, notifications aren't showing in firefox
        # I think possibly it's because we run under tox, and maybe it needs to connect to some bus or something
        ff_options.set_preference("alerts.useSystemBackend", value=False)

        # ff_options.binary_location = ''  # set custom path here
        # e.g. use firefox from here to test https://www.mozilla.org/en-GB/firefox/developer/
        if headless:
            ff_options.add_argument('--headless')
        driver = webdriver.Firefox(options=ff_options)

        addon_id = driver.install_addon(str(addon_source), temporary=True)
        logger.debug(f'firefox addon id: {addon_id}')

        version_data = {}
        # TODO 'binary'? might not be present?
        for key in ['browserName', 'browserVersion', 'moz:geckodriverVersion', 'moz:headless', 'moz:profile']:
            version_data[key] = driver.capabilities[key]
        version_data['driver_path'] = getattr(driver.service, '_path')
    elif browser == 'chrome':
        cr_options = webdriver.ChromeOptions()

        # in case user wants some adhoc override
        chrome_bin: str | None = None  # default (e.g. apt version)

        # NOTE: regular/stable chrome, --load-extension isn't working anymore
        # https://stackoverflow.com/questions/25064523/load-extension-parameter-for-chrome-doesnt-work

        if chrome_bin is not None:
            cr_options.binary_location = chrome_bin
        else:
            # TODO enable it back? for now relying on docker provided version on github actions
            # selenium manager should download latest "chrome for testing"
            # cr_options.browser_version = 'dev'

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

        # generally 'selenium manager' download the correct driver version itself
        chromedriver_bin: str | None = None  # default

        service = webdriver.ChromeService(executable_path=chromedriver_bin)
        driver = webdriver.Chrome(service=service, options=cr_options)

        version_data = {}
        # TODO 'binary'? might not be present?
        for key in ['browserName', 'browserVersion']:
            version_data[key] = driver.capabilities[key]
        version_data['chromedriverVersion'] = driver.capabilities['chrome']['chromedriverVersion']
        version_data['userDataDir'] = driver.capabilities['chrome']['userDataDir']
        version_data['driver_path'] = getattr(driver.service, '_path')

        _browser_version = tuple(map(int, version_data['browserVersion'].split('.')))
        _driver_version = tuple(map(int, version_data['chromedriverVersion'].split(' ')[0].split('.')))
    else:
        raise RuntimeError(f'Unexpected browser {browser}')
    version_string = ' '.join(f'{k}={v}' for k, v in version_data.items())
    logger.info(f'webdriver version: {version_string}')
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
        yield res
