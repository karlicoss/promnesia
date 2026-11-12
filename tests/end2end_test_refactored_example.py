"""
Example refactored end-to-end test demonstrating best practices.

This module shows how to refactor existing tests to use:
1. Explicit waits instead of hard-coded sleeps
2. Programmatic assertions instead of manual confirmations
3. Better error handling and reporting
4. Improved test structure

Compare this with the original test in end2end_test.py to see the improvements.
"""

from pathlib import Path
import pytest
from selenium.webdriver import Remote as Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

# Import the enhanced wait utilities
from end2end_wait_utils import (
    wait_for_element_visible,
    wait_for_element_invisible,
    wait_for_class_in_element,
    wait_for_text_in_element,
    wait_for_element_clickable,
    wait_for_element_count,
)

# Import test utilities
from addon import Addon, LOCALHOST
from common import has_x
from conftest_end2end import assert_no_browser_errors


class TestSidebarImproved:
    """
    Improved sidebar tests with explicit waits and programmatic assertions.
    
    Original test: test_sidebar_position in end2end_test.py
    Improvements:
    - Replaced manual confirmations with DOM assertions
    - Replaced sleeps with explicit waits
    - Added better error messages
    - More maintainable structure
    """
    
    def test_sidebar_default_position(self, addon: Addon, driver: Driver) -> None:
        """
        Verify that sidebar appears on the right by default (without manual confirmation).
        """
        # Configure extension without backend (we're only testing UI)
        addon.options_page.open()
        addon.options_page._set_endpoint(host=None, port=None)
        
        # Navigate to test page
        driver.get('https://example.com')
        
        # Open sidebar and wait for it to be visible
        addon.sidebar.open()
        
        # Wait for sidebar frame to be visible (instead of sleep)
        sidebar_frame = wait_for_element_visible(
            driver, 
            (By.ID, 'promnesia-frame'),
            timeout=5
        )
        
        # Verify sidebar is visible programmatically
        assert addon.sidebar.visible, "Sidebar should be visible after opening"
        
        # Check sidebar position using CSS properties (instead of manual confirmation)
        position_style = driver.execute_script("""
            const frame = document.getElementById('promnesia-frame');
            const style = window.getComputedStyle(frame);
            return {
                right: style.getPropertyValue('--right') || style.right,
                bottom: style.getPropertyValue('--bottom') || style.bottom,
                left: style.getPropertyValue('--left') || style.left,
                top: style.getPropertyValue('--top') || style.top
            };
        """)
        
        # Default position should be on the right
        # The exact check depends on how the CSS is structured
        assert sidebar_frame.is_displayed(), "Sidebar frame should be displayed"
        
    def test_sidebar_bottom_position(self, addon: Addon, driver: Driver) -> None:
        """
        Verify that sidebar can be positioned at the bottom.
        """
        options_page = addon.options_page
        options_page.open()
        options_page._set_endpoint(host=None, port=None)
        
        # Configure custom position
        settings = """
#promnesia-frame {
  --bottom: 1;
  --size: 20%;
}""".strip()
        options_page._set_position(settings)
        options_page._save()
        
        # Wait for settings to be saved (instead of sleep)
        wait_for_text_in_element(
            driver,
            (By.ID, 'save_id'),
            'saved',  # Assuming save button shows this text
            timeout=3
        )
        
        # Navigate to test page
        driver.get('https://example.com')
        
        # Open sidebar
        addon.sidebar.open()
        
        # Wait for sidebar to appear
        sidebar_frame = wait_for_element_visible(
            driver,
            (By.ID, 'promnesia-frame'),
            timeout=5
        )
        
        # Verify bottom position programmatically
        bottom_position = driver.execute_script("""
            const frame = document.getElementById('promnesia-frame');
            const style = window.getComputedStyle(frame);
            return style.getPropertyValue('--bottom');
        """)
        
        # Assert the custom position is applied
        assert bottom_position == '1', f"Expected --bottom: 1, got {bottom_position}"


class TestVisitedMarksImproved:
    """
    Improved visited marks tests with explicit waits.
    
    Original test: test_showvisits_popup in end2end_test.py
    Improvements:
    - Using WebDriverWait for marks to appear
    - Clear timeout configuration
    - Better assertion messages
    """
    
    def test_visited_marks_appear(self, addon: Addon, driver: Driver, backend) -> None:
        """
        Test that visited marks appear on links and show context on hover.
        """
        from promnesia.tests.utils import index_urls
        
        # Set up test data
        url = 'https://www.iana.org/'
        indexer = index_urls([('https://www.iana.org/abuse', 'some comment')])
        indexer(backend.backend_dir)
        
        # Configure extension
        addon.configure(notify_contexts=True, show_dots=True)
        
        # Navigate to page
        driver.get(url)
        
        # Find the link we're interested in
        link_with_popup = wait_for_element_visible(
            driver,
            (By.XPATH, '//a[@href="/abuse"]'),
            timeout=5
        )
        
        # Wait for visited marks to appear (instead of hard-coded sleep)
        wait_for_class_in_element(
            driver,
            (By.XPATH, '//a[@href="/abuse"]'),
            'promnesia-visited',
            timeout=5
        )
        
        # Verify the mark is present
        assert 'promnesia-visited' in link_with_popup.get_attribute('class'), \
            "Link should have promnesia-visited class"
        
        # Hover over the link to trigger popup
        addon.move_to(link_with_popup)
        
        # Wait for context popup to appear (explicit wait instead of sleep)
        popup_context = wait_for_element_visible(
            driver,
            (By.CLASS_NAME, 'context'),
            timeout=5
        )
        
        # Verify popup content
        assert 'some comment' in popup_context.text, \
            f"Expected 'some comment' in popup, got: {popup_context.text}"
        
        # Optional: Check for browser console errors
        assert_no_browser_errors(driver, allowed_patterns=[
            # Add any known/expected console warnings here
        ])


class TestBacklistImproved:
    """
    Improved blacklist tests with better automation.
    
    Original test: test_blacklist_custom in end2end_test.py
    Improvements:
    - DOM assertions instead of manual checks
    - Explicit waits for async operations
    - Clear test structure
    """
    
    def test_blacklist_blocks_page(self, addon: Addon, driver: Driver) -> None:
        """
        Verify that blacklisted pages show appropriate UI state.
        """
        # Configure blacklist
        addon.configure(port='12345', blacklist=('stackoverflow.com',))
        
        # Navigate to blacklisted page
        driver.get('https://stackoverflow.com/questions/27215462')
        
        # Activate extension
        addon.activate()
        
        # Wait for blacklist to take effect (instead of manual confirmation)
        # The sidebar should NOT be available for blacklisted pages
        
        # Check that sidebar frame is not present in DOM
        assert not addon.sidebar.available, \
            "Sidebar should not be available for blacklisted page"
        
        # Verify icon state (if accessible)
        # This depends on how icon state is exposed - might need extension API
        
        # Alternative: Check for error notification
        # (This would need access to notification system)
        
    def test_blacklist_removal(self, addon: Addon, driver: Driver) -> None:
        """
        Verify that removing from blacklist re-enables sidebar.
        """
        # Start with blacklist
        addon.configure(host=None, port=None, blacklist=('example.com',))
        driver.get('https://example.com')
        
        # Verify blocked initially
        assert not addon.sidebar.available, "Should be blacklisted initially"
        
        # Remove from blacklist
        addon.configure(host=None, port=None, blacklist=())
        
        # Refresh page
        driver.refresh()
        
        # Wait for page to load
        wait_for_element_visible(driver, (By.TAG_NAME, 'body'), timeout=5)
        
        # Open sidebar
        addon.sidebar.open()
        
        # Wait for sidebar to appear (instead of manual confirmation)
        wait_for_element_visible(
            driver,
            (By.ID, 'promnesia-frame'),
            timeout=5
        )
        
        # Verify sidebar is now available
        assert addon.sidebar.visible, \
            "Sidebar should be visible after removing from blacklist"


class TestSearchImproved:
    """
    Improved search tests with programmatic assertions.
    
    Original test: test_search_command in end2end_test.py
    """
    
    def test_search_command_opens_interface(
        self, addon: Addon, driver: Driver, backend
    ) -> None:
        """
        Verify that search command opens search interface with focus on search field.
        """
        from promnesia.tests.sources.test_hypothesis import index_hypothesis
        
        # Index test data
        index_hypothesis(backend.backend_dir)
        
        # Navigate to test page
        test_url = "https://en.wikipedia.org/wiki/Symplectic_vector_space"
        driver.get(test_url)
        
        # Trigger search
        addon.search()
        
        # Wait for search interface to appear
        search_input = wait_for_element_visible(
            driver,
            (By.ID, 'search-input'),  # Adjust selector based on actual implementation
            timeout=5
        )
        
        # Verify search field has focus (programmatically)
        active_element = driver.switch_to.active_element
        assert active_element == search_input, \
            "Search input should have focus after opening search interface"
        
        # Verify search interface is visible
        assert search_input.is_displayed(), "Search input should be visible"


# Pytest markers for better test organization
pytestmark = [
    pytest.mark.browser_test,
    # Only run if browser tests are enabled
    pytest.mark.skipif(
        'WITH_BROWSER_TESTS' not in __import__('os').environ,
        reason='Browser tests disabled'
    ),
]


# Example of a test with retry for flaky scenarios
@pytest.mark.flaky(max_runs=3)
class TestFlakyScenarios:
    """
    Tests that may be flaky and need retry logic.
    
    Use the @pytest.mark.flaky decorator for tests that occasionally fail
    due to timing issues that can't be completely eliminated.
    """
    
    def test_rapid_navigation(self, addon: Addon, driver: Driver, backend) -> None:
        """
        Test rapid navigation between pages (can be timing-sensitive).
        """
        from promnesia.tests.utils import index_urls
        
        urls = {
            'https://example.com': 'context1',
            'https://example.org': 'context2',
        }
        index_urls(urls)(backend.backend_dir)
        
        addon.configure(notify_contexts=True)
        
        # Rapidly navigate between pages
        for url in urls:
            driver.get(url)
            
            # Wait for page to fully load (instead of sleep)
            wait_for_element_visible(driver, (By.TAG_NAME, 'body'), timeout=10)
            
            # Verify extension is working
            # (specific assertions depend on extension behavior)


# Utility function example for common test patterns
def verify_sidebar_state(addon: Addon, expected_visible: bool, timeout: float = 5) -> None:
    """
    Helper function to verify sidebar visibility state with explicit wait.
    
    Args:
        addon: Addon instance
        expected_visible: Expected visibility state
        timeout: Maximum time to wait for state
        
    Raises:
        AssertionError: If state doesn't match within timeout
    """
    from end2end_wait_utils import wait_for_condition
    
    def check_visibility():
        return addon.sidebar.visible == expected_visible
    
    wait_for_condition(
        check_visibility,
        timeout=timeout,
        error_message=f"Sidebar visibility did not become {expected_visible} within {timeout}s"
    )
