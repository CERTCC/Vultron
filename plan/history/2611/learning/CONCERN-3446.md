---
source: CONCERN-3446
timestamp: '2026-11-06T22:35:39.911952+00:00'
title: 'concern: BT-18 gives a refusing call-out point no channel for a payload or
  a cause'
type: learning
---

Theme: theme:capability-architecture — gives a refusing call-out point a channel for a reason and payload.

## Summary

`BT-18` defines a call-out point backend's answer as `Status.SUCCESS` or
`Status.FAILURE` and nothing else. `BT-18-002` defines blackboard outputs
**only for the SUCCESS case**, and `BT-18-011` forbids `RUNNING`. A backend that
refuses therefore has no sanctioned way to say *anything* about its refusal.

Two distinct gaps follow from that one missing channel.

### Gap 1 — a refusal cannot carry a reason (CP-06-004)

`CP-06-004` requires the proposer to "surface the rejection reason where one is
given". After #3399 the **read** path exists and is tested:
`CaseProposalDeclineRecord.reason` → the `Reject`'s `summary`
(`_EmitRejectCaseProposalNode._call_factory`). Nothing writes it.
`_RecordProposalDeclineNode` constructs the record with `proposal_id`,
`case_actor_id` and `vendor_uri` only, so `reason` is structurally always `None`
and `summary=reason` always sends nothing.

The only test exercising the read path hand-seeds a record via `dl.save()` — a
state no production path can produce. So `CaseProposalDeclineRecord.reason` and
its read side are currently **unreachable code**, and the field's CP-06-004
docstring claim is unrealisable.

### Gap 2 — "backend unavailable" is indistinguishable from "policy declined", and the resulting refusal is permanent

In `create_case_proposal_received_tree`, `Inverter("ProposalDeclined")` maps
*any* `FAILURE` from the guarded backend to "decline". An injected backend that
returns `FAILURE` because it could not reach its policy service produces a
durable `CaseProposalDeclineRecord` that is never expired, retracted or
overridden:

- `_CheckNoDeclineRecordNode` blocks the accept arm from then on, and
- `_RecordProposalDeclineNode` is deliberately idempotent, so a later successful
  evaluation cannot correct it.

**Failure scenario**: a 30-second policy-service outage permanently and
irrevocably refuses every `CaseProposal` received in that window, with no
operator remedy short of deleting rows by hand.

This is notable because the rest of the admission gate is careful to distinguish
"no" from "I could not tell" — `_CheckProposalAlreadyAnsweredNode` deliberately
raises rather than returning `FAILURE` for exactly that reason. The seam the
policy actually arrives through is the one place the distinction cannot be
expressed.

## Why these are one issue

Both are the same missing primitive: a refusing call-out point has no channel
for a **payload** (Gap 1: the reason) or a **cause** (Gap 2: declined vs.
undeterminable). Designing one channel answers both; designing them separately
would almost certainly produce two incompatible mechanisms.

## Blast radius

- `specs/behavior-tree-integration.yaml` BT-18 (the contract itself), and
  BT-18-007 / BT-18-011, which currently pin the binary answer
- `vultron/core/behaviors/call_out/protocol.py` (`CallOutBackendFactory`) and
  `guard.py` (the `SynchronousCallOut` runtime guard)
- the five shape mixins in `vultron/demo/fuzzer/call_out_point.py`
- **66 factory fields across 17 bundles** in
  `vultron/core/behaviors/call_out/bundles/` — every existing call-out point
  inherits whatever answer shape is chosen
- ADR-0025 (call-out point abstraction), likely needing an amendment

## Suggested shape (not decided here)

1. Permit a declared **failure-output** key set alongside the SUCCESS set in
   BT-18-001/002, written only on `FAILURE`.
2. Distinguish *refused* from *undeterminable* at the seam. `BT-18-011` already
   establishes the precedent that a mis-answering backend **raises** rather than
   returning a status, so "undeterminable" plausibly raises while "refused"
   returns `FAILURE` — which would make the case-proposal gate fail the tree on
   an unreachable policy service instead of recording a permanent decline.
3. Revisit whether a permanent `CaseProposalDeclineRecord` needs an expiry or a
   retraction path once (2) can distinguish the two causes.

## Provenance

Found by review of #3428, which implemented the CaseProposal admission gate
(#3399) and hit both halves. #3399 is closed by that PR, so this issue carries
the remainder — the docs page
`docs/topics/behavior_logic/use-cases/propose-case.md` points here for the
stated gap.

Design notes captured in
`plan/incoming/learnings/20260918-3399-bt18-has-no-contract-for-a-refusal-carrying-a-payload.md`.

**Resolved**: 2026-11-06 — implementation tracked in #6076, #6077, #6078. ADR-0183: every call-out backend answers yes, no or error with typed data; the seam writes a refusal payload on no and raises on error, so an outage leaves the message in holding instead of recording a decline.

Docs PR: https://github.com/CERTCC/Vultron/pull/6082.
Notes: `notes/call-out-configuration.md`.
