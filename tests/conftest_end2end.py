"""
Pytest plugin for end-to-end test enhancements.

This conftest provides:
1. Automatic screenshot capture on test failure
2. Browser console log capture on failure
3. Enhanced error reporting for WebDriver tests
"""

import logging
from pathlib import Path
from typing import Any

import pytest
from selenium.webdriver import Remote as Driver

logger = logging.getLogger(__name__)

# Directory to save test artifacts (screenshots, logs)
ARTIFACTS_DIR = Path(__file__).parent / 'test_artifacts'


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Any:
    """
    Hook to capture screenshots and logs on test failure.
    
    This runs after each test phase (setup, call, teardown) and captures
    browser state if the test failed and a WebDriver instance is available.
    """
    # Execute the test
    outcome = yield
    report = outcome.get_result()
    
    # Only capture on actual test failure (not setup/teardown)
    if report.when == "call" and report.failed:
        # Try to get driver from test fixtures
        driver = item.funcargs.get('driver')
        if driver and isinstance(driver, Driver):
            _capture_failure_artifacts(item, driver)


def _capture_failure_artifacts(item: pytest.Item, driver: Driver) -> None:
    """
    Capture screenshots, HTML, and browser logs on test failure.
    
    Args:
        item: The pytest test item
        driver: The Selenium WebDriver instance
    """
    # Create artifacts directory if it doesn't exist
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    
    # Generate base filename from test name
    test_name = item.nodeid.replace('::', '_').replace('/', '_')
    timestamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    base_filename = f"{test_name}_{timestamp}"
    
    # Capture screenshot
    try:
        screenshot_path = ARTIFACTS_DIR / f"{base_filename}_screenshot.png"
        driver.save_screenshot(str(screenshot_path))
        logger.info(f"Screenshot saved to: {screenshot_path}")
        
        # Attach to pytest report if pytest-html is available
        if hasattr(item.config, '_html'):
            from pytest_html import extras
            item.config._html.append(extras.image(str(screenshot_path)))
    except Exception as e:
        logger.warning(f"Failed to capture screenshot: {e}")
    
    # Capture page source (HTML)
    try:
        html_path = ARTIFACTS_DIR / f"{base_filename}_page_source.html"
        html_path.write_text(driver.page_source, encoding='utf-8')
        logger.info(f"Page source saved to: {html_path}")
    except Exception as e:
        logger.warning(f"Failed to capture page source: {e}")
    
    # Capture browser console logs
    try:
        logs = driver.get_log('browser')
        if logs:
            log_path = ARTIFACTS_DIR / f"{base_filename}_browser_console.log"
            with log_path.open('w') as f:
                for entry in logs:
                    f.write(f"[{entry['level']}] {entry['timestamp']}: {entry['message']}\n")
            logger.info(f"Browser console logs saved to: {log_path}")
            
            # Log severe errors to pytest output
            severe_logs = [log for log in logs if log['level'] == 'SEVERE']
            if severe_logs:
                logger.error(f"Found {len(severe_logs)} SEVERE browser console errors:")
                for log in severe_logs:
                    logger.error(f"  {log['message']}")
    except Exception as e:
        logger.warning(f"Failed to capture browser logs: {e}")
    
    # Capture WebDriver logs (if available)
    try:
        driver_logs = driver.get_log('driver')
        if driver_logs:
            driver_log_path = ARTIFACTS_DIR / f"{base_filename}_driver.log"
            with driver_log_path.open('w') as f:
                for entry in driver_logs:
                    f.write(f"[{entry['level']}] {entry['timestamp']}: {entry['message']}\n")
            logger.info(f"WebDriver logs saved to: {driver_log_path}")
    except Exception as e:
        # Driver logs might not be available for all browsers
        pass
    
    # Capture current URL and window info
    try:
        info_path = ARTIFACTS_DIR / f"{base_filename}_browser_info.txt"
        with info_path.open('w') as f:
            f.write(f"Current URL: {driver.current_url}\n")
            f.write(f"Window handles: {driver.window_handles}\n")
            f.write(f"Current window: {driver.current_window_handle}\n")
            
            # Try to get window size
            try:
                size = driver.get_window_size()
                f.write(f"Window size: {size}\n")
            except:
                pass
            
            # Try to get browser capabilities
            try:
                f.write(f"\nCapabilities:\n")
                for key, value in driver.capabilities.items():
                    f.write(f"  {key}: {value}\n")
            except:
                pass
        
        logger.info(f"Browser info saved to: {info_path}")
    except Exception as e:
        logger.warning(f"Failed to capture browser info: {e}")


@pytest.fixture(scope='session', autouse=True)
def cleanup_old_artifacts():
    """
    Clean up old test artifacts at the start of test session.
    
    Keeps the artifacts directory clean by removing files older than 7 days.
    """
    if ARTIFACTS_DIR.exists():
        import time
        cutoff_time = time.time() - (7 * 24 * 60 * 60)  # 7 days ago
        
        removed_count = 0
        for artifact_file in ARTIFACTS_DIR.iterdir():
            if artifact_file.is_file() and artifact_file.stat().st_mtime < cutoff_time:
                try:
                    artifact_file.unlink()
                    removed_count += 1
                except Exception as e:
                    logger.warning(f"Failed to remove old artifact {artifact_file}: {e}")
        
        if removed_count > 0:
            logger.info(f"Removed {removed_count} old test artifacts")


def pytest_configure(config: pytest.Config) -> None:
    """
    Register custom markers for end-to-end tests.
    """
    config.addinivalue_line(
        "markers",
        "browser_test: mark test as a browser-based end-to-end test"
    )
    config.addinivalue_line(
        "markers", 
        "flaky(max_runs=3): mark test as flaky with automatic retry"
    )


# Optional: Add a utility function to assert no console errors
def assert_no_browser_errors(driver: Driver, allowed_patterns: list[str] | None = None) -> None:
    """
    Assert that there are no SEVERE errors in browser console.
    
    Args:
        driver: Selenium WebDriver instance
        allowed_patterns: Optional list of error message patterns to ignore
        
    Raises:
        AssertionError: If severe errors are found in console
    """
    allowed_patterns = allowed_patterns or []
    
    try:
        logs = driver.get_log('browser')
        severe_logs = [log for log in logs if log['level'] == 'SEVERE']
        
        # Filter out allowed errors
        filtered_logs = []
        for log in severe_logs:
            message = log['message']
            if not any(pattern in message for pattern in allowed_patterns):
                filtered_logs.append(log)
        
        if filtered_logs:
            error_messages = '\n'.join([f"  {log['message']}" for log in filtered_logs])
            raise AssertionError(
                f"Found {len(filtered_logs)} SEVERE browser console errors:\n{error_messages}"
            )
    except Exception as e:
        if "get_log" not in str(e):  # Only ignore if it's a get_log issue
            raise


# Optional: Add pytest command line option for artifacts directory
def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Add custom command line options.
    """
    parser.addoption(
        "--artifacts-dir",
        action="store",
        default=str(ARTIFACTS_DIR),
        help="Directory to save test failure artifacts (screenshots, logs, etc.)"
    )


@pytest.fixture(scope='session')
def artifacts_dir(request: pytest.FixtureRequest) -> Path:
    """
    Provide artifacts directory path to tests.
    """
    artifacts_path = Path(request.config.getoption("--artifacts-dir"))
    artifacts_path.mkdir(exist_ok=True)
    return artifacts_path
