---
source: ISSUE-1917
timestamp: '2026-08-04T13:34:22.069555+00:00'
title: CaseActor RM lifecycle bootstrap (CM-23-005/006/007)
type: implementation
---

## Issue #1917 — CaseActor CaseParticipant RM lifecycle bootstrap

Implemented CM-23-005/006/007 and ADR-0051. The CaseActor's `_AddCaseActorParticipantNode` now emits three bootstrap `ParticipantStatus` records (RM.RECEIVED → RM.VALID → RM.ACCEPTED) during case initialization. `_CommitNativeLedgerEntriesNode` picks these up automatically as `CaseLedgerEntry` records. Removed the obsolete `CVDRole.CASE_MANAGER` skip from `AllParticipantsRMClosedConditionNode` so the CaseActor's RM.CLOSED now participates in the all-closed check.

5 new tests added; 3 regression tests updated. 6050 tests passing.

PR: <https://github.com/CERTCC/Vultron/pull/1965>
