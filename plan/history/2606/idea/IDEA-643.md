---
source: IDEA-643
timestamp: '2026-06-11T19:22:16.025887+00:00'
title: SYNC integration test expansion for single-peer replication cycle
type: idea
---

## Summary

The sync spec (SYNC-07-002, SYNC-07-003) requires integration tests covering
the full single-peer CaseActor → Participant replication cycle. Currently,
`test/core/use_cases/received/test_sync.py` and
`test/core/behaviors/sync/` contain unit tests for isolated components, but
no integration test covers the end-to-end network flow: the CaseActor appends
a log entry, sends an `Announce(CaseLogEntry)` activity, and the receiving
Participant validates the predecessor hash and appends the entry to its
replica.

SYNC-07-003 additionally requires coverage of conflict and idempotency
scenarios: mismatched predecessor hash, duplicate delivery, and leader retry
after rejection.

## Acceptance Criteria

- [ ] AC-1: Add a `@pytest.mark.integration` test that spins up two actors
  (CaseActor and one Participant) and verifies the full replication cycle:
  append → Announce → validate → append to replica.
- [ ] AC-2: Test covers SYNC-03-001 (receiver rejects on predecessor hash
  mismatch) and SYNC-03-002 (leader retries from last-accepted entry).
- [ ] AC-3: Test covers SYNC-03-003 idempotency: duplicate delivery of the
  same entry does not create a duplicate in the receiver's log.
- [ ] AC-4: Tests are tagged `@pytest.mark.integration` and run in CI via
  the full `pytest -m ""` suite.

## Reference

Spec: `specs/sync-log-replication.yaml` SYNC-07-002, SYNC-07-003,
SYNC-03-001, SYNC-03-002, SYNC-03-003

**Processed**: 2026-06-11 — implementation tracked in #901, #902, #903.
