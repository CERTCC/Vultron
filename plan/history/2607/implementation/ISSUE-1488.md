---
source: ISSUE-1488
timestamp: '2026-07-17T18:14:41.401315+00:00'
title: ISSUE-1488 extract factory calls to _emit() helpers
type: implementation
---

## Issue #1488 — inline factory calls exceed BTND-07-003 god-node limit

Refactored 6 BT leaf node files, extracting inline factory calls from `update()` methods into named helpers (`_emit`, `_call_factory`, `_emit_accept`, `_emit_close_case`). All `update()` bodies reduced to ≤30 lines.

Code review (pre-PR) caught one correctness regression: `ProposeCaseToActorNode._emit()` incorrectly moved `record_outbox_item` inside the try/except, which would have silenced outbox failures and allowed duplicate CaseProposal retries. Fixed before the PR opened.

Follow-up #1492 created for full AC-3 compliance (`EmitSubmitReportActivity` extending `_EmitCaseActorReportActivityBase`).

PR: <https://github.com/CERTCC/Vultron/pull/1493>
