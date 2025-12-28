---
name: End-to-End Test Improvement
about: Track specific improvements to browser-based end-to-end tests
title: '[E2E Test] '
labels: testing, end-to-end
assignees: ''
---

## Test to Improve

**Test name:** `test_<name>` (or describe the test scenario)

**File:** `tests/end2end_test.py` (or other file)

**Current issue:**
- [ ] Uses hard-coded sleep() calls
- [ ] Requires manual confirmation
- [ ] Is marked as xfail/skip
- [ ] Is flaky (fails intermittently)
- [ ] Other: _describe_

## Proposed Improvement

**What to change:**
<!-- Describe the specific improvement -->

**Expected benefit:**
- [ ] Improved reliability
- [ ] Faster execution
- [ ] Better automation (less manual steps)
- [ ] Easier maintenance
- [ ] Other: _describe_

## Implementation Approach

**Use these utilities/patterns:**
- [ ] Replace sleeps with explicit waits from `end2end_wait_utils.py`
- [ ] Convert manual confirmations to DOM assertions
- [ ] Add proper error handling
- [ ] Refactor following examples in `end2end_test_refactored_example.py`
- [ ] Other: _describe_

## Code Example

```python
# Before:
# <current problematic code>

# After:
# <improved code>
```

## Related Issues

<!-- Link to related test improvement issues -->

## Acceptance Criteria

- [ ] No hard-coded sleep() calls
- [ ] No manual confirmations (or documented as necessary)
- [ ] Test passes consistently (3+ runs)
- [ ] Clear assertion messages
- [ ] Follows patterns from refactored examples

## References

- [End-to-End Test Improvements Guide](../doc/END2END_TEST_IMPROVEMENTS.md)
- [Wait Utilities](../tests/end2end_wait_utils.py)
- [Refactored Examples](../tests/end2end_test_refactored_example.py)
