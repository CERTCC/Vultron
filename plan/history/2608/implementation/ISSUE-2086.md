---
source: ISSUE-2086
timestamp: '2026-08-08T01:49:37.124299+00:00'
title: Fix demo config cache leak causing flaky bootstrap validate-report
type: implementation
---

**Issue**: [#2086](https://github.com/CERTCC/Vultron/issues/2086) — Flaky CI:
`TestBootstrapSequence.test_announce_creates_case_replica` /
`test_case_fields_preserved_in_replica` — `SvcValidateReportUseCase` no
routable recipients.

**PR**: [#2126](https://github.com/CERTCC/Vultron/pull/2126)

## Symptoms

Two `test/demo/test_pcr_bootstrap.py` tests failed intermittently in CI with
`SvcValidateReportUseCase: no routable recipients`. Secondary symptom:
`EnsureEmbargoExists` reporting no active embargo. Passed in isolation.

## Root cause

Not a race and not a production defect. `vultron/config/app.py` keeps a
process-global `_config_cache`; `reload_config()` clears it and re-reads the
environment. Pytest's `monkeypatch` fixture undoes env changes *after* the
requesting fixture's teardown body runs, so a teardown that calls
`reload_config()` before the undo re-caches the still-patched value for the
remainder of the session.

Four demo fixtures had that order, repointing `VULTRON_SERVER__BASE_URL` and
`VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL` at fake hosts. Every later demo test
then derived its CaseActor ID from the leaked host (e.g.
`http://coordinator-otc.test`), which no `_TestClientRouter` registers.
`_TestClientRouter.emit` silently dropped the `Create(CaseProposal)` at DEBUG
level, so the CaseActor never created the canonical case with its
`CASE_MANAGER` participant and embargo, and `trigger/validate-report` failed
three steps downstream. Because it only affects tests running after the
offender and `pytest-randomly` reseeds order per run, it read as flakiness.

## Fix

- Reordered teardown to `monkeypatch.undo()` before `reload_config()` in
  `test_fvcv_handoff_demo.py`, `test_pcr_late_joiner.py`,
  `test_case_proposal_round_trip.py`, `test_pcr_engage_case.py`.
  `test_fv_demo.py` already avoided the trap via an explicit `MonkeyPatch()`.
- Added `config_url_snapshot()` / `restore_config_if_leaked()` plus an autouse
  `restore_case_actor_url_after_each_test` fixture in `test/demo/conftest.py`
  that snapshots the two URLs around every demo test and reloads on drift.
- Added `test/demo/test_config_leak_guard.py` (5 tests) covering both teardown
  orderings, the guard helpers, and the demo session's baseline CaseActor URL.

No production code changed.

## Discarded approach

An initial fix made `_compute_report_addressees` fall through to the offer
actor when a case had no `CASE_MANAGER`. It was reverted: it broke the
fail-closed routing invariant from issue #1854 AC-2, asserted by
`test_close_report_raises_when_case_exists_without_case_manager`.

## Verification

Deterministic repro with `-p no:randomly`; 16/16 pass after the fix. Unit
suite 6453 passed. Integration suite 1050 passed, with 2 pre-existing
`test_integration_script_scenarios.py` failures reproduced on a clean
`origin/main` worktree and tracked by
[#2122](https://github.com/CERTCC/Vultron/issues/2122). Black, flake8, mypy,
pyright clean.

## Learnings

- `20260808-silent-delivery-drop-masks-config-leak.md` (`signal: concern`)
- `20260808-module-level-config-cache-fragile-in-tests.md` (`signal: concern`)
