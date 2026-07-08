"""
Enhanced wait utilities for end-to-end tests.

This module provides robust waiting mechanisms to replace hard-coded sleeps
and reduce test flakiness.
"""

from collections.abc import Callable
from time import time, sleep
from typing import TypeVar, Any

from selenium.webdriver import Remote as Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

T = TypeVar('T')

# Default timeout for all wait operations (can be overridden)
DEFAULT_TIMEOUT = 10
DEFAULT_POLL_INTERVAL = 0.1


def wait_for_condition(
    condition_func: Callable[[], bool | T],
    timeout: float = DEFAULT_TIMEOUT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    error_message: str = "Condition not met within timeout",
) -> T | bool:
    """
    Wait for a condition function to return a truthy value.
    
    Args:
        condition_func: Function that returns True/truthy when condition is met
        timeout: Maximum time to wait in seconds
        poll_interval: Time between condition checks in seconds
        error_message: Error message if timeout is reached
        
    Returns:
        The truthy value returned by condition_func
        
    Raises:
        TimeoutError: If condition is not met within timeout
    """
    end_time = time() + timeout
    last_exception = None
    
    while time() < end_time:
        try:
            result = condition_func()
            if result:
                return result
        except Exception as e:
            last_exception = e
        sleep(poll_interval)
    
    if last_exception:
        raise TimeoutError(f"{error_message}. Last exception: {last_exception}")
    raise TimeoutError(error_message)


def wait_for_element_visible(
    driver: Driver,
    locator: tuple[str, str],
    timeout: float = DEFAULT_TIMEOUT,
) -> WebElement:
    """
    Wait for an element to be visible in the DOM.
    
    Args:
        driver: Selenium WebDriver instance
        locator: Tuple of (By.*, value) for element location
        timeout: Maximum wait time in seconds
        
    Returns:
        The visible WebElement
    """
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located(locator),
        message=f"Element {locator} not visible within {timeout}s",
    )


def wait_for_element_invisible(
    driver: Driver,
    locator: tuple[str, str],
    timeout: float = DEFAULT_TIMEOUT,
) -> bool:
    """
    Wait for an element to become invisible or removed from DOM.
    
    Args:
        driver: Selenium WebDriver instance
        locator: Tuple of (By.*, value) for element location
        timeout: Maximum wait time in seconds
        
    Returns:
        True when element is invisible
    """
    return WebDriverWait(driver, timeout).until(
        EC.invisibility_of_element_located(locator),
        message=f"Element {locator} still visible after {timeout}s",
    )


def wait_for_element_count(
    driver: Driver,
    locator: tuple[str, str],
    count: int,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[WebElement]:
    """
    Wait for a specific number of elements matching the locator.
    
    Args:
        driver: Selenium WebDriver instance
        locator: Tuple of (By.*, value) for element location
        count: Expected number of elements
        timeout: Maximum wait time in seconds
        
    Returns:
        List of WebElements when count matches
    """
    def check_count():
        elements = driver.find_elements(*locator)
        if len(elements) == count:
            return elements
        return None
    
    result = wait_for_condition(
        check_count,
        timeout=timeout,
        error_message=f"Expected {count} elements matching {locator}, got different count",
    )
    return result if result else []


def wait_for_attribute_value(
    element: WebElement,
    attribute: str,
    expected_value: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> bool:
    """
    Wait for an element's attribute to have a specific value.
    
    Args:
        element: WebElement to check
        attribute: Attribute name
        expected_value: Expected attribute value
        timeout: Maximum wait time in seconds
        
    Returns:
        True when attribute matches expected value
    """
    return wait_for_condition(
        lambda: element.get_attribute(attribute) == expected_value,
        timeout=timeout,
        error_message=f"Attribute '{attribute}' did not become '{expected_value}' within {timeout}s",
    )


def wait_for_text_in_element(
    driver: Driver,
    locator: tuple[str, str],
    text: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> bool:
    """
    Wait for specific text to appear in an element.
    
    Args:
        driver: Selenium WebDriver instance
        locator: Tuple of (By.*, value) for element location
        text: Text to wait for
        timeout: Maximum wait time in seconds
        
    Returns:
        True when text is found in element
    """
    return WebDriverWait(driver, timeout).until(
        EC.text_to_be_present_in_element(locator, text),
        message=f"Text '{text}' not found in element {locator} within {timeout}s",
    )


def wait_for_element_clickable(
    driver: Driver,
    locator: tuple[str, str],
    timeout: float = DEFAULT_TIMEOUT,
) -> WebElement:
    """
    Wait for an element to be clickable (visible and enabled).
    
    Args:
        driver: Selenium WebDriver instance
        locator: Tuple of (By.*, value) for element location
        timeout: Maximum wait time in seconds
        
    Returns:
        The clickable WebElement
    """
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(locator),
        message=f"Element {locator} not clickable within {timeout}s",
    )


def wait_for_class_in_element(
    driver: Driver,
    locator: tuple[str, str],
    class_name: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> WebElement:
    """
    Wait for a specific CSS class to be present on an element.
    
    Args:
        driver: Selenium WebDriver instance
        locator: Tuple of (By.*, value) for element location
        class_name: CSS class name to wait for
        timeout: Maximum wait time in seconds
        
    Returns:
        The WebElement when class is present
    """
    def check_class():
        element = driver.find_element(*locator)
        classes = element.get_attribute('class') or ''
        if class_name in classes.split():
            return element
        return None
    
    result = wait_for_condition(
        check_class,
        timeout=timeout,
        error_message=f"Class '{class_name}' not found on element {locator} within {timeout}s",
    )
    return result  # type: ignore[return-value]


def wait_for_url_change(
    driver: Driver,
    old_url: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """
    Wait for the browser URL to change from the specified URL.
    
    Args:
        driver: Selenium WebDriver instance
        old_url: URL to wait to change from
        timeout: Maximum wait time in seconds
        
    Returns:
        The new URL
    """
    def check_url():
        current_url = driver.current_url
        if current_url != old_url:
            return current_url
        return None
    
    result = wait_for_condition(
        check_url,
        timeout=timeout,
        error_message=f"URL did not change from {old_url} within {timeout}s",
    )
    return result or driver.current_url


def wait_for_window_count(
    driver: Driver,
    count: int,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[str]:
    """
    Wait for a specific number of browser windows/tabs.
    
    Args:
        driver: Selenium WebDriver instance
        count: Expected number of windows
        timeout: Maximum wait time in seconds
        
    Returns:
        List of window handles when count matches
    """
    def check_windows():
        handles = driver.window_handles
        if len(handles) == count:
            return handles
        return None
    
    result = wait_for_condition(
        check_windows,
        timeout=timeout,
        error_message=f"Expected {count} windows, got different count within {timeout}s",
    )
    return result or []


def wait_for_js_condition(
    driver: Driver,
    js_condition: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """
    Wait for a JavaScript condition to return a truthy value.
    
    Args:
        driver: Selenium WebDriver instance
        js_condition: JavaScript expression to evaluate
        timeout: Maximum wait time in seconds
        
    Returns:
        The result of the JavaScript expression
        
    Example:
        wait_for_js_condition(driver, "return document.readyState === 'complete'")
    """
    def check_js():
        return driver.execute_script(js_condition)
    
    return wait_for_condition(
        check_js,
        timeout=timeout,
        error_message=f"JavaScript condition '{js_condition}' not met within {timeout}s",
    )


# Backward compatibility - keep the original wait_for_alert from webdriver_utils
# This is exported here for convenience
from webdriver_utils import wait_for_alert  # noqa: F401, E402


# Example usage in tests:
"""
# Instead of:
driver.get('https://example.com')
sleep(2)  # wait for page to load

# Use:
wait_for_js_condition(driver, "return document.readyState === 'complete'")

# Instead of:
addon.sidebar.open()
sleep(1)  # wait for sidebar to appear

# Use:
addon.sidebar.open()
wait_for_element_visible(driver, (By.ID, 'sidebar-element'))

# Instead of:
driver.find_element(By.ID, 'button').click()
sleep(0.5)  # wait for response

# Use:
wait_for_element_clickable(driver, (By.ID, 'button')).click()
wait_for_text_in_element(driver, (By.ID, 'result'), 'Success')
"""
