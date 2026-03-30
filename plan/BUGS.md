# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYYYMMDDXX` for bug IDs, where `YYYYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,  
the first bug identified on March 26, 2026 would be `BUG-2026032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

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

## BUG-2026032602 (FIXED 2026-03-26) — `uv run` fails due to `snapshot/Q1-2026` git tag

`uv run pytest` (and `uv run black`, etc.) failed to build the package because
the `snapshot-2026Q1` tag is "externally known as" `snapshot/Q1-2026` by the
remote. `git describe` returned `snapshot/Q1-2026`, which `vcs_versioning`
could not parse as a version string, causing an `AssertionError`.

### Reproduction

```bash
uv run pytest --tb=short 2>&1 | head -10
```

Produced:

```text
× Failed to build `vultron @ file:///...`
UserWarning: tag 'snapshot/Q1-2026' no version found
AssertionError
```

### Root Cause

The build backend (`vcs_versioning`, used by `setuptools-scm` in the `uv`
build environment) runs `git describe --dirty --tags --long` which returns
`snapshot/Q1-2026-...-...` (the remote alias for the local `snapshot-2026Q1`
tag). `vcs_versioning` then tries to parse `snapshot/Q1-2026` against the
`tag_regex`, gets `None`, and raises `AssertionError`. The `fallback_version`
option is not reached because the code path raises instead of returning `None`.

### Resolution

Added `git_describe_command` to `[tool.setuptools_scm]` in `pyproject.toml`
to pass `--match v[0-9]*` to `git describe`, restricting it to semver-style
tags (e.g. `v2024.4.3`) and skipping snapshot/branch tags entirely. Also
added `fallback_version = "0.0.0+dev"` as a belt-and-suspenders measure for
any future case where no version tag is reachable.

Validation: `uv run pytest --version` now succeeds and resolves to
`vultron==2024.4.4.dev1073+gbea71843`. Full suite: 1026 passed via `uv run`.

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
