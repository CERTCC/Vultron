---
source: ISSUE-1776
timestamp: '2026-07-29T19:02:20.239215+00:00'
title: Slim vendor receive_report_case_tree (ADR-0041)
type: implementation
---

## Issue #1776 — Slim vendor receive_report_case_tree: store report + send proposal only (ADR-0041)

Implemented ADR-0041 CaseActor-authoritative case initialization.

The vendor `receive_report_case_tree` now writes a pending `VultronReportCaseLink` and sends `Create(as_CaseProposal)` to the CaseActor, instead of creating a `VulnerabilityCase` directly.

New nodes: `WritePendingReportCaseLinkNode` (DataLayerAction), `CheckPendingProposalExistsForReport`, `ProposeReportCaseToActorNode` (in new `proposal.py`).

All downstream tests updated to reflect ADR-0041 behavior (pending link instead of case at receipt).

PR: <https://github.com/CERTCC/Vultron/pull/1821>
