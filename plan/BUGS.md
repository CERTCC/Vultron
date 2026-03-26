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

---

## BUG-2026032602 — `uv run` fails due to `snapshot/Q1-2026` git tag

`uv run pytest` (and `uv run black`, etc.) fail to build the package because
the `snapshot/Q1-2026` git tag is not recognized by `vcs_versioning`, causing
an `AssertionError` in `setuptools_scm`.

### Reproduction

```bash
uv run pytest --tb=short 2>&1 | head -10
```

Produces:

```text
× Failed to build `vultron @ file:///...`
UserWarning: tag 'snapshot/Q1-2026' no version found
AssertionError
```

### Workaround

Use `.venv/bin/pytest`, `.venv/bin/black`, `.venv/bin/flake8` etc. directly
instead of `uv run <tool>`.

### Root Cause

`vcs_versioning` cannot parse the `snapshot/Q1-2026` format as a version
string. Needs a version tag in standard semver format (e.g. `v2026.1.0`) to
proceed past the `snapshot/` tag.

---

## BUG-2026032603 — Test ordering dependency in `test_datalayer_isolation.py`

`TestRecordIsolation::test_two_actors_can_store_same_id_independently` fails
when run in isolation (`pytest test/adapters/driven/test_datalayer_isolation.py`)
but passes in the full suite.

### Reproduction

```bash
.venv/bin/pytest test/adapters/driven/test_datalayer_isolation.py --tb=short
```

Produces:

```text
ValueError: Type 'Note' not found in vocabulary for Record conversion
```

### Root Cause

The vocabulary registry is populated by imports that happen as a side effect
of loading other test modules. When the datalayer isolation tests run alone,
the `'Note'` type is not registered in the vocabulary, so `record_to_object`
raises `ValueError`. The test helper uses `type_='Note'` as default, but
'Note' may not be in the registry until other modules are imported.

### Workaround

Run the full suite. The full suite always passes (1026 passed).
