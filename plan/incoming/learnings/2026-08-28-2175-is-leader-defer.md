---
date: 2026-08-28
issue: "2175"
type: defer
---
# DEFER: EmitCaseStatusUpdateNode inner BTBridge ignores is_leader

During review of #2175/#2176, found that the inner `BTBridge` in
`EmitCaseStatusUpdateNode.update()` is constructed with default `is_leader=True`,
ignoring the outer execution context's leadership guard.

Tracked as #2856 (size:S).

If a non-leader actor reaches this node (outer guard relaxed), it would mint
a ledger entry it is not authorised to mint (CLP-08-005).
