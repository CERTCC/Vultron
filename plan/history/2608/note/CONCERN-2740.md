---
source: CONCERN-2740
timestamp: '2026-08-28T14:25:28.256405+00:00'
title: ValidateCaseStatusTransitionNode intentionally unwired but not removed
type: note
---

`ValidateCaseStatusTransitionNode` was intentionally unwired from `add_case_status_tree` as part of ISSUE-2256's per-dimension filter refactor (RSH-05, ADR-0061). The per-dimension filter nodes (`FilterCsEmDimensionNode`, `FilterCsPxaDimensionNode`, `FinalizeCsFilterNode`) are the correct replacement. The node had been retained as a deprecated shim in the module but never re-wired.

Resolved by PR #2805 (<https://github.com/CERTCC/Vultron/pull/2805>), which removed `ValidateCaseStatusTransitionNode` and its RM counterpart `CheckParticipantRMNotClosedNode` entirely per the project's no-backwards-compat-shims policy. ADR-0061 was revised in-place to replace the "Neutral, because CheckParticipantRMNotClosedNode remains deprecated..." bullet with a statement that both nodes were removed.
