---
source: CONCERN-3918
timestamp: '2026-09-30T19:05:23.793964+00:00'
title: 'ADR-0113 blast radius: relay through the CASE_MANAGER reaches every embargo
  proposal'
type: learning
---

## Problem

ADR-0113 (docs PR #3912) decided, for embargo *revisions*, that a participant's proposal goes to the CASE_MANAGER only; the CASE_MANAGER moves the canonical case, commits, and relays an `Invite(EmbargoEvent)` to every participant except the proposer; participants answer the Invite addressed to them and write no state on receipt; the owner's answer is consent and decision; replicas reconstruct every step from the ledger. The rule it rests on is general: **a ledger entry carries case state to replicas and never sets a parse-and-respond expectation; the protocol interactions the behavioural specs define still happen, relayed through the CASE_MANAGER, and each is recorded.** The three Concerns it resolved (#3892, #3836, #3863) were scoped to revisions, so EP-09 is written for revisions. The rule is not, and its reach was not audited.

## What needs investigating

Each of these is a place the rule plausibly applies and nothing yet says so:

- **The initial embargo proposal (EP, `NONE → PROPOSED`).** `SvcProposeEmbargoUseCase` addresses the first proposal to the CASE_MANAGER only and nothing relays it, so participants are never invited to the first embargo any more than to a revision. Does EP-09 generalise to EP, and does EMB-01 need the same "the Participant receiving EP is the CASE_MANAGER" mapping EMB-03 now carries?
- **RSVP deadlines and the pocket veto (CM-28, EP-07).** `_store_invite_deadline` writes the deadline onto the invitee's record at receipt. Under EP-09-003 a participant writes nothing on receipt, so the deadline must be recorded at the CASE_MANAGER's commit of the Invite emission and reach the replica through replay. Where does `detect_and_apply_lapse` run, and whose clock stamps the window?
- **EK acknowledgements (EMB-03-001, EMB-04-001, EMB-05-001, VP-11-004).** The behavioural specs have the receiver emit EK. Under the relay: does the CASE_MANAGER ack the proposer, do participants ack the CASE_MANAGER's Invite, or is the ledger entry the acknowledgement?
- **Counter-proposals (EMB-15-003, EMB-12-001).** A participant's counter-revision goes to the CASE_MANAGER and is itself a new proposal, so it triggers another relay round; several rounds interleave with `pending_embargo_proposal_index` holding several open entries (EP-08). Is the cascade bounded, and is EP-09-001's "no transition for a counter" enough?
- **The protocol-asks model (`specs/protocol-asks.yaml` ASK-01 through ASK-08, ADR-0080).** A general notion of an "ask" already exists. It should agree with "the ledger never asks" and with the relay, or one of them needs amending.
- **Received Accept/Reject embargo trees.** They run `accept_embargo_invite(OBSERVED)` and the reject tree at every inbox today. #3814 gates them behind the CASE_MANAGER; EP-09-003 says the same thing from the other direction. Confirm the two say one thing and that the consent-answer replay (#3915) covers what the gating removes.
- **Demo scenario specs DEMOMA-20 and DEMOMA-21** (`rcv-embargo`, `rcvv-embargo`, unbuilt: #2071, #2072) describe EP/EA/EV/EJ/ET exchanges in peer voice. Check whether their `steps` assume participant-to-participant delivery and amend them to the relay before the scenarios are built.
- **Emit-side optimism generally.** ADR-0113 §10 leaves the proposer's local `REVISE` write alone, as ADR-0108 left the emit side. Every trigger that writes local state before the CASE_MANAGER answers is the same shape (propose, accept, reject, terminate, status updates). Is a general statement warranted, and is any of those writes load-bearing for a demo assertion that should be reading the ledger instead?
- **`resolve_invitee_id` multi-recipient logic** exists to make one `Invite` correct in every recipient's replica. Under one Invite per participant with the CASE_MANAGER as sender, is the multi-recipient case still reachable, or is it dead code the relay retires?

## Acceptance criteria

- [ ] AC-1: Each bullet above is answered with a pointer to code and spec, and classified as: covered by ADR-0113 as written / needs a spec entry (name the group) / needs its own Concern or Task / out of scope with a reason.
- [ ] AC-2: Any generalisation that changes the communication model (initial proposal relay, EK placement, asks alignment) is recorded in ADR-0113 as an amendment or in a new ADR, per `notes/specs-vs-adrs.md`.
- [ ] AC-3: Implementation Tasks are created for every gap confirmed, wired under epic #3408 (or the epic that owns the area), and DEMOMA-20/21 are amended before #2071/#2072 start if they assume peer delivery.

## Governing specs

EP-09-001 through EP-09-007, EP-04-011, EP-08-004, EMB-01, EMB-03, EMB-15, CM-28, EP-07, PCR-08-001, PCR-08-003, RSH-08-003, RSH-08-004, ASK-01 through ASK-08, DEMOMA-20, DEMOMA-21. ADR-0113, ADR-0108, ADR-0109, ADR-0080.

## Reference

Source: planning interview for #3892, #3836, #3863 (docs PR #3912). Blocked by those three Concerns so it cannot start before ADR-0113 merges.

---

**Resolved**: 2026-09-30 — implementation tracked in #3961 (RSVP deadline stamped by the CASE_MANAGER, lapse at the manager only), #3962 (trigger-side write gate with the pending-assertion store), #3963 (invitee is the sole `to` recipient), #3964 (CASE_MANAGER role never unfilled; CM-24-003 retired); #3913 widened to the first proposal, #2884 gains the embargo-Invite ask kind, #3915 and #3814 annotated, #2071/#2072 told of the DEMOMA amendments.

Audit outcome per bullet: initial proposal — needs spec entry, folded into #3913 (EP-09-001 generalised); RSVP deadlines — needs spec entries CM-28-012/013/014 and Task #3961; EK — covered by MSM-02-009, recorded as EP-09-009, no code; counter-proposals — covered by ADR-0113 as rewritten and EP-08, no code; protocol asks — needs spec entries ASK-03-007/ASK-04-010, folded into #2884; received Accept/Reject trees — covered by #3814 and #3915; DEMOMA-20/21 — amended in the docs PR; emit-side optimism — decision changed: withdrawn for shared EM state (EP-09-008, Task #3962, ADR-0108 amended); invitee resolution — dead code, Task #3963. Plus one finding outside the list: the "no CASE_MANAGER" fallback (CM-24-003) codified a state no creation path can produce; CM-24-006 states the invariant and Task #3964 retires it.

ADR-0113 was rewritten in place rather than amended (same-day ADR).

Docs PR: <https://github.com/CERTCC/Vultron/pull/3960>.
Spec: `specs/embargo-policy.yaml` (EP-09), `specs/case-management.yaml` (CM-28, CM-24-006), `specs/protocol-asks.yaml`, `specs/em-behavior.yaml`, `specs/multi-actor-demo.yaml`.
Notes: `notes/embargo-lifecycle.md`, `notes/case-communication-model.md`, `notes/participant-embargo-consent.md`, `notes/protocol-asks.md`.
