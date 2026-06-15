---
source: ISSUE-950
timestamp: '2026-06-15T15:20:33.706164+00:00'
title: Add in-process case-ledger invariant assertions to two-actor demo test
type: implementation
---

## Issue #950 — Track A: Add case-ledger invariant assertions to in-process two-actor demo test

Extended `test/demo/test_two_actor_demo.py` with a `TestCaseLedgerInvariants` class that
asserts case-ledger invariants against live in-process DataLayer state rather than parsed
JSONL files. Tests run in ~1 s without any Docker requirement.

**Changes:**

- Added module-level import of `strip_id_prefix` from `vultron.adapters.utils`
- Added four helper functions: `_log_event_type`, `_log_payload`, `_participant_id_and_rm`,
  `_fetch_case_log`
- Added `TestCaseLedgerInvariants` with a class-scoped `completed_workflow` fixture that
  runs the full two-actor scenario (seed → report → validate → fix → publish → close),
  and three integration tests:
  - `test_add_participant_status_entries_present` — CI invariant 7 presence pre-condition
  - `test_all_participants_rm_closed_at_scenario_end` — CI invariant 7 terminal RM state
  - `test_required_event_types_present_in_case_actor_log` — baseline event-type check

**Verification:** 3 new tests pass in 1.1 s; full suite 3430 passed, 34 skipped, 5 xfailed.
Black, flake8, mypy, pyright clean.

PR: <https://github.com/CERTCC/Vultron/pull/952>
