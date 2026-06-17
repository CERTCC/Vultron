---
source: ISSUE-1021
timestamp: '2026-06-17T17:22:35.170687+00:00'
title: Centralize CASE_MANAGER gate on CommitCaseLedgerEntryNode (Inv-5 2/3)
type: implementation
---

## Issue #1021 — Inv-5 (2/3): Centralize CASE_MANAGER gate on CommitCaseLedgerEntryNode

Added `CheckIsCaseManagerNode` condition node and `create_guarded_commit_case_ledger_entry_tree`
factory, then migrated all ~10 unguarded `CommitCaseLedgerEntryNode` call sites to the
guarded factory. Ensures that only the CaseActor (participant holding `CVDRole.CASE_MANAGER`)
may commit canonical hash-chained case-ledger entries; all other actors silently skip via
a Success leaf.

Also restored the receiver-identity pre-flight check in `status.py::_commit_log_cascade_bt`
that had been accidentally removed during migration. The in-tree CASE_MANAGER gate is
insufficient there because `actor_id` is always `case_actor_id` in that path — the
Python-side `receiving_actor_id != case_actor_id` guard must be preserved.

**Outcome**: 3477 tests pass; Black, flake8, mypy, pyright all clean.

PR: [#1024](https://github.com/CERTCC/Vultron/pull/1024)
