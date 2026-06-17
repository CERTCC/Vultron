---
source: ISSUE-902
timestamp: '2026-06-11T19:56:40.979961+00:00'
title: SYNC predecessor mismatch rejection and replay integration
type: implementation
---

## Issue #902 — SYNC Integration: predecessor mismatch rejection and leader replay

Implemented end-to-end integration coverage for SYNC mismatch handling and replay recovery in `test/demo/test_sync_log_replication.py`.

The new test verifies that a participant rejects an out-of-chain `Announce(CaseLogEntry)`, reports `last_accepted_hash`, the CaseActor updates peer replication state, and replayed entries converge on the participant replica. It also asserts actor app DataLayer isolation.

PR: <https://github.com/CERTCC/Vultron/pull/909>
