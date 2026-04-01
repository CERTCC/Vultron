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

## BUG-2026040101 (FIXED 2026-04-01) — Invited case participants do not reach `RM.ACCEPTED`

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

`AcceptInviteActorToCaseReceivedUseCase` created a `VultronParticipant` with
empty `participant_statuses`. When read back from the DataLayer as a wire-layer
`CaseParticipant`, the `init_participant_status_if_empty` validator seeded the
participant at `RM.START`. The `engage-case` trigger then attempted
`START → ACCEPTED` which is an invalid RM transition (the state machine only
allows `VALID → ACCEPTED` or `DEFERRED → ACCEPTED`).

Additionally, `VultronParticipant` lacked an `append_rm_state` method, meaning
it did not fully satisfy the `ParticipantModel` Protocol.

### Resolution

1. Added `append_rm_state` method to `VultronParticipant`
   (`vultron/core/models/participant.py`) to mirror the wire-layer
   `CaseParticipant.append_rm_state`, making the domain type structurally
   compatible with the `ParticipantModel` Protocol.
2. In `AcceptInviteActorToCaseReceivedUseCase.execute()`
   (`vultron/core/use_cases/received/actor.py`), pre-seed the new participant
   with `RM.RECEIVED` then `RM.VALID` states before persisting. Accepting an
   invitation is semantically equivalent to having received and validated the
   case, so these two states are correct precursors to `RM.ACCEPTED`.
3. Added regression test
   `TestInviteActorUseCases::test_accept_invite_participant_can_reach_rm_accepted`
   in `test/core/use_cases/received/test_actor.py`.

Validation: 1200 passed, 5581 subtests; black/flake8/mypy/pyright all clean.

---

## BUG-2026040102 (FIXED 2026-04-01) — Circular import causes `test_performance.py` to fail

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

---

## BUG-2026040103 (FIXED 2026-04-01) — `ResourceWarning: unclosed file` for `mydb.json` in test suite

The full test run emits multiple `ResourceWarning: unclosed file <mydb.json>`
messages after the pytest session summary. These are printed directly to stderr
by the Python interpreter at shutdown (via "Exception ignored in:" machinery),
not via `warnings.warn()`. The project's `filterwarnings = ["error"]` config
catches `warnings.warn()` calls but does NOT catch these teardown-time
`ResourceWarning` messages. Consequently the warnings appear in CI output but
do not cause test failures—yet they indicate that TinyDB file handles are not
being cleaned up.

### Reproduction

```bash
uv run pytest --tb=short 2>&1 | grep ResourceWarning | head -5
```

### Root Cause

`TestGetDatalayerFactory` (in `test/adapters/driven/test_datalayer_isolation.py`)
calls `get_datalayer()` with no arguments, which creates a file-backed
`TinyDbDataLayer` at `mydb.json`. The singleton caches these instances, but no
test or fixture closes them before session teardown. The `cleanup_test_db_files`
session fixture in `test/conftest.py` removes `mydb.json` from disk but does
not call `reset_datalayer()` or `dl.close()` first, so TinyDB holds open file
handles until the Python interpreter shuts down.

### Resolution Steps

This is not the first time we've seen issues with test pollution from the
file-backed datalayer. It would be ideal if we could ensure through the use
of fixtures or context managers that any file-backed datalayer instances are
both properly closed and removed after each test that uses them to prevent
this kind of pollution and resource leakage. The exact implementation may
vary from the suggested steps below, which were noted based on the most
recent instance of the problem. If there is a more general solution that
ensures that we won't see this again, we should do that instead.

1. In `test/conftest.py`'s `cleanup_test_db_files` fixture, call
   `reset_datalayer()` before deleting `mydb.json` so all cached
   `TinyDbDataLayer` instances are closed before the file is removed.
2. Optionally, add a `scope="function"` autouse fixture to
   `test/adapters/driven/conftest.py` that calls `reset_datalayer()` after
   each test in `TestGetDatalayerFactory` so file-backed singletons are not
   accumulated across the class.
3. Verify that `uv run pytest --tb=short 2>&1 | grep ResourceWarning` produces
   no output after the fix.

### Resolution

1. Rewrote `test_datalayer_serialization.py` fixtures to use
   `get_datalayer(db_path=None)` (in-memory), inject the instance into FastAPI
   via `dependency_overrides`, and call `reset_datalayer()` in teardown. Test
   bodies updated to use the `datalayer` fixture parameter.
2. Updated `test/conftest.py` `cleanup_test_db_files` to call
   `reset_datalayer()` before deleting `mydb.json` in both setup and teardown
   phases.
3. Added regression test `test_test_datalayer_uses_in_memory_storage` that
   fails on file-backed storage and passes after the fix.

Validation: `uv run pytest --tb=short 2>&1 | grep -i ResourceWarning` → no
output; 1201 passed, 5581 subtests; black/flake8/mypy/pyright clean.
