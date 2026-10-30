import warnings
from collections.abc import Generator
from pprint import pformat

import pytest


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Function) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    if report.when not in ('setup', 'call') or not report.failed:
        return report

    driver = item.funcargs.get('driver')
    if driver is None:
        return report

    # Selenium is only installed for the browser tests.
    from selenium.webdriver.common.by import By
    from selenium.webdriver.remote.webdriver import WebDriver

    if not isinstance(driver, WebDriver):
        return report

    details = {}
    try:
        details['url'] = driver.current_url
        details['title'] = driver.title
        details['body'] = driver.find_element(By.TAG_NAME, 'body').text[:1000]
    except Exception as error:
        # Diagnostics must not hide the original test failure if the browser is unavailable.
        details['error'] = f'{type(error).__name__}: {error}'
    report.sections.append(('Browser diagnostics', pformat(details, sort_dicts=False)))
    return report


@pytest.fixture(autouse=True)
def ignore_warnings():
    ## This is coming from HPI since we use tmp_config stuff
    # Hmm looking at it, the whole thing is pretty annoying...
    # I think maybe instead what should happen is
    # - if my.config is already present _and_ it's not the stub config, just use it
    # - only otherwise try messing with it
    warnings.filterwarnings("ignore", message="'my.config' package isn't found!")
    ##
    ## These are coming from hypothesis data access layer, doesn't matter for tests
    warnings.filterwarnings("ignore", message="You might want to 'pip install colorlog'")
    warnings.filterwarnings("ignore", message="recommended to 'pip install ijson'")
    warnings.filterwarnings("ignore", message="recommended to 'pip install orjson'")
    ##
