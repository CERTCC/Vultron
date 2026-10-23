---
source: ISSUE-1834
timestamp: '2026-07-31T13:55:45.820732+00:00'
title: 'fix(case-proposal): correct context/in_reply_to field assignment'
type: implementation
---

## Issue #1834 — fix(case-proposal): correct context/in_reply_to field assignment on Create(VulnerabilityCase)

Corrected the CP-05-003/ADR-0045 field assignment violation in `_WriteCreateCaseMarkerNode`.
`Create(VulnerabilityCase)` now emits `context=case_uri, in_reply_to=accept_uri` (was: `context=accept_uri`).
This fixes a CaseProposal bootstrap deadlock caused by the inbox deferral router mistaking the Accept URI for a case ID.

PR: <https://github.com/CERTCC/Vultron/pull/1852>
