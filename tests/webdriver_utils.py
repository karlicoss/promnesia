#!/usr/bin/env python3
from contextlib import contextmanager
from typing import Optional, Iterator


from selenium.webdriver import Remote as Driver
from selenium.webdriver.remote.webelement import WebElement


def get_current_frame(driver: Driver) -> Optional[WebElement]:
    # idk why is it so hard to get current frame in selenium, but it is what it is
    # https://github.com/seleniumhq/selenium-google-code-issue-archive/issues/4305#issuecomment-192026569
    return driver.execute_script('return window.frameElement')


@contextmanager
def frame_context(driver: Driver, frame) -> Iterator[Optional[WebElement]]:
    # todo return the frame maybe?
    current = get_current_frame(driver)
    driver.switch_to.frame(frame)
    try:
        new_frame = get_current_frame(driver)
        yield new_frame
    finally:
        driver.switch_to.frame(current)


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
