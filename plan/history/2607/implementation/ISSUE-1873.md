---
source: ISSUE-1873
timestamp: '2026-07-31T19:01:32.255399+00:00'
title: retire silent-drop on genesis-unavailable — send Reject (SYNC-15)
type: implementation
---

Fixes #1873. Root cause: `ReconstructChainTailNode` returned `FAILURE` when `VulnerabilityCase` was not yet seeded on the Finder replica (CLP-08-005); the `ProcessAndStore` Sequence exited before `SendRejectLogEntryNode` ran, so the `CaseLedgerEntry` was permanently dropped — the CaseActor never knew to replay.

Fix: write sentinel values (`tail_hash=""`, `tail_index=-1`) to the blackboard before returning `FAILURE`; wrap `ReconstructChainTailNode` in a `ReconstructOrRejectOnMissingCase` Selector whose fallback is `SendRejectLogEntryNode`. The Reject carries `last_accepted_hash=""` (replay from genesis), matching the SYNC-08-005 pattern.

Added SYNC-15 spec group (SYNC-15-001 MUST send Reject; SYNC-15-002 MUST NOT persist) and regression test `test_missing_case_queues_reject_with_empty_tail_hash`. Demo gains `wait_for_case_on_container` checkpoint before ledger coverage wait for fast CI failure isolation.

PR: <https://github.com/CERTCC/Vultron/pull/1889>
