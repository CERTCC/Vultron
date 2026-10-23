---
source: CONCERN-1970
timestamp: '2026-08-05T15:32:30.882957+00:00'
title: 'Demo integration bugs are only detectable in CI: seven pytest coverage gaps
  prevent local chain-level testing'
type: learning
---

## Summary

The test suite cannot reproduce the bugs and protocol inconsistencies that
surface during demo integration runs. Seven concrete coverage gaps mean a
breakage caught in seconds locally (pytest) is instead discovered after a
10–20 minute CI cycle, often requiring multiple rounds. This concern tracks
all seven gaps and requests a systematic leftward shift of that detection
boundary.

## Surface Symptom vs. Underlying Problem

**Surface symptom:** Several classes of bugs are only found when running full
Docker-compose demo runs in CI. The cycle time (10–20 min/round, multiple
rounds common) makes iteration expensive.

**Underlying problem:** The test suite is structured around individual
component isolation (each use-case or BT node tested alone, each state
machine tested against a fresh DataLayer) but the protocol bugs that matter
most emerge from *chains* of operations across actors. The demo run is the
only harness that exercises these chains end-to-end. The invariant ratchet
tests in `test/ci/invariants/` exist and are well-designed but skip unless
`devlogs/` is present. The milestone verification helpers in
`demo/helpers/milestones.py` and `demo/helpers/verification.py` contain
exactly the assertions needed, but they are wired only to the live demo —
not to the TestClient-backed demo tests.

What is already correct and should be left untouched: the per-use-case
trigger tests, the architecture invariant tests, and the existing TestClient
demo tests all form a solid foundation. The fix is to connect them more
tightly to the cross-cutting chains, not to replace or restructure them.

## Seven Gaps

- **Gap 1**: Invariant ratchet tests require devlogs/ to run — 15 invariant
  functions are CI-only without synthetic fixtures
- **Gap 2**: Demo TestClient tests assert only final state, not intermediate
  milestones from `demo/helpers/milestones.py`
- **Gap 3**: No use-case chain tests; only per-use-case isolation; TODO
  comment in `test_reporting_workflow.py`
- **Gap 4**: PEC invite→accept chain only exercised in full demos; no
  regression guard for PEC direct-assignment pitfall
- **Gap 5**: Outbox addressing (PCR-08-001) unasserted in case trigger
  use-case tests
- **Gap 6**: Participant-state predicate logic embedded in demo HTTP helpers,
  not testable in isolation
- **Gap 7**: `check_late_joiner_has_full_history` edge cases (gap before
  join, out-of-order delivery, empty replica) unexercised

**Resolved**: 2026-08-05 — implementation tracked in #1976, #1977.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1975>.
Notes: `notes/triggers-test-coverage.md`, `vultron/core/behaviors/AGENTS.md`.
