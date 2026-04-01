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

---

## BUG-2026040101 — Invited case participants do not reach `RM.ACCEPTED`

The D5-3 three-actor demo exposed a state-model mismatch for participants
added through `AcceptInviteActorToCaseReceivedUseCase`.

### Reproduction

1. Seed a case in the authoritative case container.
2. Deliver `RmInviteToCaseActivity` to a remote actor and then deliver
   `RmAcceptInviteToCaseActivity` back to the authoritative case container.
3. Trigger `POST /actors/{actor_id}/trigger/engage-case` for that invited
   participant on the same case.
4. Inspect the resulting `CaseParticipant.participant_statuses`.

Observed behavior: the participant is added to `case.case_participants` and
`actor_participant_index`, but their current RM state does not end at
`RM.ACCEPTED`.

### Root Cause

`AcceptInviteActorToCaseReceivedUseCase` creates a generic `VultronParticipant`
with the default participant-status initialization. That leaves the new
participant on a status history that does not align cleanly with the
`engage-case` trigger's `update_participant_rm_state(..., RM.ACCEPTED, ...)`
expectation for invited participants.

### Follow-up

- Decide the intended post-invite RM lifecycle for invited participants.
- Either seed the participant with the correct initial RM state/role-specific
  participant type, or adjust the engage/invite transition logic so an invited
  participant can reach `RM.ACCEPTED` deterministically.

---

## BUG-2026040102 — Circular import causes `test_performance.py` to fail

`test/core/behaviors/test_performance.py` fails to collect (ImportError)
when run in isolation, and fails as part of the full `uv run pytest` suite.

### Reproduction

```bash
uv run pytest test/core/behaviors/test_performance.py --tb=short
```

Produces:

```text
ImportError: cannot import name 'create_validate_report_tree' from partially
initialized module 'vultron.core.behaviors.report.validate_tree'
(most likely due to a circular import)
```

### Root Cause

Circular import chain:

```text
test_performance.py
  → vultron.core.behaviors.report.validate_tree
    → vultron.core.behaviors.report.nodes
      → vultron.core.use_cases.triggers._helpers
        → vultron.core.use_cases.triggers (via __init__)
          → vultron.core.use_cases.triggers.report
            → vultron.core.behaviors.report.validate_tree  ← CIRCULAR
```

`validate_tree` is not yet fully initialized when `triggers.report` tries
to import `create_validate_report_tree` from it. The full test suite
sometimes passes because other test modules pre-load `validate_tree` before
`test_performance.py` is collected; in isolation or unlucky ordering the
partial-module import error surfaces.

### Resolution Steps

1. Break the cycle by moving the `validate_tree` import in `triggers.report`
   to a local (deferred) import, OR refactor so `triggers.report` does not
   directly import from `validate_tree` (e.g., accept the tree as a
   constructor argument or use a factory function in a neutral module).
2. Follow the AGENTS.md guidance: prefer refactoring over lazy imports, but
   a local import is acceptable as a last resort if refactoring is impractical.
3. Verify `test_performance.py` collects and passes both in isolation and as
   part of the full suite.
