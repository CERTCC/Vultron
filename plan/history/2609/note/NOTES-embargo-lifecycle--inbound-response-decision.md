---
source: NOTES-embargo-lifecycle--inbound-response-decision
timestamp: '2026-09-17T17:22:59.311559+00:00'
title: Inbound Embargo-Response Decision (EMB-15)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) built; #1942/#1983/#1257 closed
**Superseded by:** vultron/core/behaviors/embargo/response_decision_tree.py; specs/embargo-policy.yaml EMB-15

---

## Inbound Embargo-Response Decision (EMB-15)

**Status**: Implemented — PR #1983 / issue #1942. Spec group `EMB-15` in
`specs/em-behavior.yaml`; call-out catalog in
`notes/bt-fuzzer-nodes-embargo.md`.

### Two overture flows the simulator conflated

The pre-PEC simulator collapsed embargo-response into a single
`_ChooseEmProposedResponse` fallback (`vultron/bt/embargo_management/behaviors.py`).
The production protocol separates two distinct inbound overtures:

| | **Flow A — EM proposal** | **Flow B — PEC invitation** |
|---|---|---|
| Inbound message | `ProposeEmbargo` / EP | `InviteToEmbargoOnCase` |
| Question asked | "here are terms" | "become a signatory to this embargo" |
| Accept advances | shared EM (`NONE → PROPOSED → ACTIVE`) | this participant's PEC (`INVITED → SIGNATORY`) |
| Accept mechanism | `accept_embargo_trigger_bt` | `accept_invite_to_embargo_tree` |
| Reject mechanism | `reject_embargo_trigger_bt` (ER; EM → NONE) | `reject_invite_to_embargo_tree` (PEC → DECLINED) |
| Status | **decision layer missing** | mechanics built, **decision layer missing** |

The mechanical BTs for both flows already exist and are purely
transition-recording — they act on whatever arrived. What is missing (and
what #1257 adds) is the **decision layer** that chooses *how to respond*,
layered over both flows as a single seam.

### Design: default-accept with an owner-adjudication seam

Mirrors the two-seam authorization model (ADR-0046) and
`case_proposal_received_tree` (CASE_OWNER gospel bypass → owner-approval
call-out → deterministic default):

```text
Selector (response decision):
  Sequence("AcceptArm"):
    Selector("Authorize"):
      CheckIsCaseOwner            # hard bypass — owner's response is gospel (EMB-15-002)
      CaseOwnerApprovesEmbargoResponse   # call-out; DETERMINISTIC → SUCCESS
    EvaluateEmbargoProposal       # call-out; DETERMINISTIC → SUCCESS (accept, EMB-15-001)
    → delegate to flow-appropriate accept BT
  Sequence("CounterArm"):         # Flow A only (EMB-15-003)
    WillingToCounterEmbargoProposal   # call-out; DETERMINISTIC → FAILURE (off by default)
    → delegate to propose_embargo_trigger_bt (counter = re-propose; no new mechanism)
  RejectArm:                      # (EMB-15-004)
    → delegate to reject_embargo_trigger_bt (Flow A) / reject_invite_to_embargo_tree (Flow B)
```

Hard rule: EMB-01-002 (reject when CS is public/exploit/attacks) overrides the
default-accept policy regardless of adjudication outcome.

### Policy: "shortest embargo wins, then propose extensions"

The recommended CVD default is to **accept** an offered embargo rather than
counter, and negotiate extensions/revisions separately (accept-then-revise).
This is why `EvaluateEmbargoProposal` defaults to accept and
`WillingToCounterEmbargoProposal` defaults to *not* counter. A future
adjudication backend (UI or LLM agent) may poll other participants, apply an
organizational "shortest-embargo-wins" rule, or defer to the case owner — but
that logic lives behind the call-out points, not in the tree.

### Not overtaken; not a monolithic port

Unlike the original Idea framing (one `create_propose_embargo_decision_tree`
mirroring `_ProposeEmbargoBt` + `_ChooseEmProposedResponse` +
`_ChooseEmActiveResponse` as a tick-loop), the outbound "want to propose /
select terms" decision is already the propose trigger use case plus thin
call-out seams in `create_manage_embargo_tree`, and the **active-embargo
review loop** (`CurrentEmbargoAcceptable`) is a continuous-monitoring
Sentinel with no event trigger — tracked separately for monitoring
epic #1147 (companion Idea to #1257), not built here.
