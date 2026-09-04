---
title: "DEFER: EmitCaseStatusUpdateNode inner BTBridge ignores is_leader"
type: learning
timestamp: "2026-08-28T19:29:30Z"
source: ISSUE-2175
signal: concern
---
# DEFER: EmitCaseStatusUpdateNode inner BTBridge ignores is_leader

During review of #2175/#2176, found that the inner `BTBridge` in
`EmitCaseStatusUpdateNode.update()` is constructed with default `is_leader=True`,
ignoring the outer execution context's leadership guard.

Tracked as #2856 (size:S).

If a non-leader actor reaches this node (outer guard relaxed), it would mint
a ledger entry it is not authorised to mint (CLP-08-005).

## Audit disposition (2026-09-02)

Tracked as #2856 (still open).
