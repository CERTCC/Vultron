# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## BUG-2026032601 (FIXED 2026-03-26)

`uv run pytest` produces a warning about `TestEnum` in `test/bt/test_behaviortree/test_common.py`:

```text
test/bt/test_behaviortree/test_common.py:37
  /Users/adh/Documents/git/vultron_pub/test/bt/test_behaviortree/test_common.py:37: PytestCollectionWarning: cannot collect test class 'TestEnum' because it has a __init__ constructor (from: test/bt/test_behaviortree/test_common.py)
    class TestEnum(enum.IntEnum):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1025 passed, 1 warning, 5581 subtests passed in 24.30s
```

### Resolution

- Renamed the helper enum in
  `test/bt/test_behaviortree/test_common.py` from `TestEnum` to `MockEnum`
  so pytest no longer tries to collect it as a test class.
- Added `test/test_pytest_collection_hygiene.py` to prevent helper enums in
  `test/` from using `Test*` names that trigger `PytestCollectionWarning`.
- Validation: `uv run pytest --tb=short 2>&1 | tail -5` now reports
  `1026 passed, 5581 subtests passed` with no warning summary.
