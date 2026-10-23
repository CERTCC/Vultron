---
source: CONCERN-4632
timestamp: '2026-10-15T20:40:19.652909+00:00'
title: Embargo received trees refuse without telling the sender (CLP-02-005)
type: learning
---

## Summary

CLP-02-005 says a refusal by the CASE_MANAGER "MUST be emitted as a `Reject` protocol activity directed at the asserting participant".
No embargo received tree does this.
Each one reports its refusal only through the handler result (`HandlerResult.refused`), and none passes `refusal_effects` to `create_receive_activity_tree` (CLP-10-022).
That covers:

- `Reject(Invite(EmbargoEvent))`: a Reject of an embargo that is neither active nor open, and (from #4388) a signatory's Reject of the embargo in force;
- `Accept`/`Reject(EmbargoEvent, target=Case)`: the owner's decision on an embargo that is not an open proposal;
- `Leave(EmbargoEvent)` (#4388): a withdrawal from an embargo not in force, from a row that is not `AGREED`, or from the case owner.

The only trees with sender feedback today are the RM ones (`rm_gap_note`).

## Why it matters

A sender whose assertion is refused never learns why, and its pending assertion stays open until it times out.
The triggers check the same predicates before sending, so a well-behaved sender is rarely refused, but a raced or stale sender is.

## The open question

Which activity answers each refusal?
Answering a `Leave(EmbargoEvent)` with `Reject(Leave(EmbargoEvent))` would be a new message type, and the sender's side would need a pattern and a use case for it, like `Reject(Leave(VulnerabilityCase))` (CM-23-017).
A `Note`, as the RM trees send, needs none of that but is not the `Reject` CLP-02-005 names.
The decision should cover every embargo tree at once rather than one at a time.

Found while building #4388.

Governing specs: CLP-02-005, CLP-10-022, HP-01-006, MSM-07-004, MSM-07-010

**Resolved**: 2026-10-15. Implementation is tracked in #4754, #4755 and #4756.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4753>.
Spec: `specs/case-ledger-processing.yaml` (CLP-05-001, CLP-06-006 and CLP-10-022 amended; ADR-0141).
Notes: `notes/case-ledger-authority.md`.

Decision: every refusal by a precondition guard at the CASE_MANAGER is answered with one refusal notice, a `Reject` whose object is the refused activity inline. The sender closes its pending assertion when the notice arrives. A `Reject(Invite)` or `Reject(Offer)` from the CASE_MANAGER is read as both a decline and a refusal. The other options were one `Reject` type per refused message and a directed `Note`; both were rejected. The mechanism and the embargo trees are planned now, and the remaining received trees follow under #4756.
