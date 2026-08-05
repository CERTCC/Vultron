---
source: ISSUE-1959
timestamp: '2026-08-05T15:06:52.218572+00:00'
title: 'fix(embargo): handle EM PROPOSED in PublicDisclosureBranchNode P/X/A cascade'
type: implementation
---

## Issue #1959 — fix(embargo): handle EM PROPOSED in PublicDisclosureBranchNode P/X/A cascade

Fixed root-cause bug in `_PublicDisclosureSkipConditionNode` where `case.active_embargo is None`
silently skipped teardown in EM PROPOSED state (active_embargo is always None when only a proposed
embargo exists). Now reads `case.current_status.em.state` directly via `_em_state()` helper.

`PublicDisclosureBranchNode` now uses a `TeardownSelector` routing to either `terminate_embargo_bt`
(ACTIVE/REVISE) or the new `reject_proposed_embargo_bt` (PROPOSED), implementing EMB-16-001.

New nodes: `IsProposedEmbargoNode`, `ReadProposedEmbargoIdNode`, `RejectProposedEmbargoLifecycleNode`,
`SendRejectEmbargoActivityNode` — extracted to `reject_proposed.py` for BTND-07-004 compliance.

14 tests (9 new): unit tests for all 5 skip-condition cases (AC-4) + integration test verifying
EM→NONE transition and ER outbox queueing (AC-5). All 6097 tests pass.

PR: <https://github.com/CERTCC/Vultron/pull/1974>
