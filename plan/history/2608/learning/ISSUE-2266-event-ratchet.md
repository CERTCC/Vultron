---
title: A structural ratchet was added for DEMOMA-16-008 because no obtainable CI signal could verify it
type: learning
timestamp: 2026-08-12T00:00:00Z
source: ISSUE-2266-event-ratchet
signal: design-question
---

## Decision

ISSUE-2266 asked for a spec amendment (AC-1), nine test-constant edits (AC-2/AC-3),
and two notes-table updates (AC-4) — no new test file. It also stated that a green
`Invariant Harness` job is not obtainable and MUST NOT be the verification bar, and
that AC-2/AC-3 should be verified "by inspection and by unit tests over `common.py`".

Inspection alone is not a regression guard, and `common.py` unit tests cannot see the
per-scenario constants — `check_event_type_present()` is given the list, it does not
own it. So the acceptance criteria as written would have landed with nothing able to
fail if a tenth scenario arrived without the universal block, or if `engage_case` were
dropped from one harness again. That is the same hole that let PR #2018 add
`engage_case` to one harness without amending the spec.

Added `test/ci/invariants/test_universal_event_types.py`: it reads
`.github/demo-scenarios.json`, imports each named harness module, and asserts the
constant opens with the five DEMOMA-16-001 types (each exactly once), plus that
DEMOMA-16-001's statement still enumerates exactly those five. It runs in the ordinary
unit suite with no devlogs and no demo, so it is a signal that is actually obtainable
locally and in CI — unlike the harness job it protects.

## Why it matters

DEMOMA-16-008 ("spec and test constants change in the same PR") was a prose rule with
no enforcement for its whole life. Rules of that shape are what CONCERN-2243 is about:
the belief that something is checked, where nothing checks it.

The design constraint worth preserving: `notes/demo-ci-invariants.md` forbids a second
scenario registry (a `conftest.py` mapping was specced in DEMOMA-19-008 and never
existed — CONCERN-2004). Driving the ratchet off the CI matrix honors that; a hardcoded
list of nine harness files inside the test would have re-created exactly the registry
the notes prohibit. Anyone extending this test should keep reading the matrix.

Verified the ratchet fails on drift before finalizing it, rather than trusting that a
passing new test is a working new test.

**Promoted**: 2026-08-17 — captured in ratchet test implemented in PR #2266; tracked.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>0>0>0>0>0>0>0>0>0>.
