# End-to-End Test Improvements

This directory contains improved utilities and examples for browser-based end-to-end tests.

## 📚 Documentation

**[Complete Improvement Guide](../doc/END2END_TEST_IMPROVEMENTS.md)** - Comprehensive analysis and suggestions

## 🛠️ Utilities

### Wait Utilities (`end2end_wait_utils.py`)

Robust waiting mechanisms to replace hard-coded sleeps:

```python
from end2end_wait_utils import (
    wait_for_element_visible,
    wait_for_element_clickable,
    wait_for_text_in_element,
    wait_for_condition,
)

# Wait for element to be visible
element = wait_for_element_visible(driver, (By.ID, 'sidebar'))

# Wait for custom condition
wait_for_condition(lambda: addon.sidebar.visible, timeout=5)
```

### Auto-Capture Plugin (`conftest_end2end.py`)

Automatically captures screenshots, HTML, and logs on test failure:

- Screenshots saved to `tests/test_artifacts/`
- Browser console logs captured
- Page source saved for debugging
- No configuration needed - just import!

## 📖 Examples

### Refactored Test Examples (`end2end_test_refactored_example.py`)

See real examples of improved tests:

- ✅ Explicit waits instead of sleeps
- ✅ Programmatic assertions instead of manual confirmations
- ✅ Better error messages
- ✅ Proper test structure

## 🚀 Quick Start

1. **Replace sleeps with waits:**
   ```python
   # Before
   sleep(2)
   
   # After
   wait_for_element_visible(driver, (By.ID, 'element'))
   ```

2. **Enable auto-capture:**
   ```python
   # Already works! Just run tests and check test_artifacts/ on failure
   ```

3. **Use refactored patterns:**
   ```python
   # See end2end_test_refactored_example.py for complete examples
   ```

4. **Run tests in parallel:**
   ```bash
   pytest -n auto tests/end2end_test.py
   ```

## 📊 Key Improvements

| Area | Before | After |
|------|--------|-------|
| **Waits** | `sleep(2)` | `wait_for_element_visible(...)` |
| **Assertions** | Manual confirmation | Programmatic DOM checks |
| **Debugging** | Limited context | Screenshots + logs on failure |
| **Speed** | Sequential | Parallel execution ready |

## 🔗 Related Files

- `tests/end2end_test.py` - Original tests (to be gradually refactored)
- `tests/webdriver_utils.py` - Existing WebDriver utilities
- `tests/addon.py` - Addon helper classes
- `.github/ISSUE_TEMPLATE/end2end_test_improvement.md` - Issue template for tracking improvements

## 📝 Contributing

To improve a test:

1. Review the [improvement guide](../doc/END2END_TEST_IMPROVEMENTS.md)
2. Use utilities from `end2end_wait_utils.py`
3. Follow patterns from `end2end_test_refactored_example.py`
4. Create an issue using the [template](../.github/ISSUE_TEMPLATE/end2end_test_improvement.md)

## 🎯 Goals

- **Reliability**: No flaky tests due to timing issues
- **Speed**: Faster test execution through parallelization
- **Automation**: Maximum automation, minimum manual checks
- **Maintainability**: Clear, well-structured test code
