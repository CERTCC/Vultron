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

## BUG-2026032603 (FIXED 2026-03-26) — Test ordering dependency in `test_datalayer_isolation.py`

`TestRecordIsolation::test_two_actors_can_store_same_id_independently` failed
when run in isolation (`pytest test/adapters/driven/test_datalayer_isolation.py`)
but passed in the full suite.

### Reproduction

```bash
.venv/bin/pytest test/adapters/driven/test_datalayer_isolation.py --tb=short
```

Produced:

```text
ValueError: Type 'Note' not found in vocabulary for Record conversion
```

### Root Cause

The vocabulary registry is populated by imports that happen as a side effect
of loading other test modules. When the datalayer isolation tests ran alone,
the `'Note'` type was not registered in the vocabulary, so `record_to_object`
raised `ValueError`. The test helper uses `type_='Note'` as default, but
'Note' was not in the registry until other modules were imported.

Additionally, `_object_from_storage` only caught `ValidationError`, allowing
`ValueError` from `record_to_object` to propagate unchecked.

### Resolution

1. **`test/adapters/driven/conftest.py`**: moved `as_Note` import from inside
   the `note_object` fixture body to module level, so `Note` is registered in
   the vocabulary whenever conftest loads (before any test in the package runs).
2. **`vultron/adapters/driven/datalayer_tinydb.py`**: broadened the exception
   catch in `_object_from_storage` from `except ValidationError` to
   `except (ValidationError, ValueError)` so unknown-vocabulary types fall
   through to the remaining fallbacks instead of propagating.

Validation: `test/adapters/driven/test_datalayer_isolation.py` now passes
in isolation (29 passed) and full suite remains 1026 passed.
