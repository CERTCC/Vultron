---
source: CONCERN-1832
timestamp: '2026-07-30T18:31:34.090912+00:00'
title: CONCERN-1832 — AS2 context vs inReplyTo on Create(VulnerabilityCase)
type: learning
---

## Summary

CP-05-003 incorrectly placed the `Accept(CaseProposal)` URI in the `context`
field of `Create(VulnerabilityCase)`. AS2 defines `context` as a
scoping/grouping key (must be the case URI for all case-scoped activities)
and `inReplyTo` as the causal antecedent field.

## Root Cause

The original ADR-0023 choice predated two system-wide invariants that were
established later:

1. The 29-site `context = case URI` convention across all case-scoped activities
2. The inbox deferral router's assumption that `context` always carries the case
   URI (`_activity_context_id()` in `inbox_pending_queue.py`)

When `context = Accept URI`, the deferral guard reads the Accept URI as the
"case ID", finds no `VulnerabilityCase` under that key, and defers the bootstrap
`Create(VulnerabilityCase)` — causing a deadlock: nothing will ever unblock the
deferred queue for a case that will never be created.

## Resolution

- Amended CP-05-003 (`specs/case-proposal.yaml`): `context` MUST be the case URI;
  `in_reply_to` MUST carry the `Accept(CaseProposal)` URI
- Added ADR-0045 recording the corrected field assignment and rationale
- Appended "Field Assignment Correction" section to ADR-0023 clarifying its
  remaining valid scope (protocol structure, not field assignment)
- Corrected `notes/case-proposal.md` protocol flow and rationale
- Added "AS2 Field Conventions: context vs inReplyTo" section to
  `notes/activitystreams-semantics.md`

## References

- Docs PR: <https://github.com/CERTCC/Vultron/pull/1833>
- Implementation issue: #1834
- ADR: `docs/adr/0045-create-vulnerability-case-field-assignment.md`
- Spec: `specs/case-proposal.yaml` CP-05-003 (amended)
