---
status: proposed
date: 2026-07-09
deciders: [adh, Copilot]
---

# ADR-0026: CaseActor-Routed Actor Suggestion and Invitation Flow

## Context and Problem Statement

When a case participant wants to suggest that another actor be invited to the case,
how should the suggestion be communicated so that (1) the CaseActor can record the event
in the canonical ledger, (2) the Case Owner receives the suggestion and can approve or
reject it, and (3) the approved invitation follows the existing invite/accept/bootstrap
chain?

The current prototype implementation (`suggest_actor_tree.py`,
`suggest_actor_demo.py`) routes the suggestion `Offer(Actor, Case)` directly to the
Case Owner's inbox. This predates the CaseActor routing model established in
ADR-0021 and PCR-08: all case-scoped protocol activity MUST route through the
CaseActor's inbox so it can record the event in the canonical ledger before
broadcasting to participants.

## Decision Drivers

- All case-scoped messages MUST route through the CaseActor inbox (ADR-0021,
  PCR-08-001, PCR-08-002).
- The Case Owner is the sole decision-maker for case participant membership; no
  participant can invite directly without Case Owner approval (CM-02-001).
- The CaseActor MUST commit a ledger entry for every received and every sent
  protocol activity (CLP-07, CLP-10-006 ordering rule).
- The invited actor MUST have enough information to give informed consent to the
  active embargo before accepting the invitation (issue #1289, MV-10-006).
- Invited participants MUST carry the roles the Case Owner intends for them
  (issue #1288).

## Considered Options

### Option A: Direct-to-owner routing (current prototype behavior)

The recommending participant sends `Offer(Actor, Case)` directly to the Case
Owner's inbox. The Case Owner's BT checks `case.attributed_to == actor_id` and
either emits an `AcceptActorRecommendation + RmInviteToCase` or a
`RejectActorRecommendation`.

- Good: simple, fewer protocol hops.
- Bad: bypasses the CaseActor; recommendation is never recorded in the canonical
  ledger.
- Bad: the Case Owner's BT must self-identify as the owner, coupling the handler
  to the authorization model in a way that other received-side use cases do not.
- Bad: there is no mechanism for the CaseActor to broadcast the recommendation
  to other participants so they have consistent ledger state.
- Bad: roles for the new participant must come from the recommender or be invented
  at accept time; neither path is specified.

### Option B: CaseActor-routed with transform (chosen)

The recommending participant sends `Offer(Actor X, Case)` to the CaseActor's
inbox. The CaseActor:

1. Records the received Offer in the ledger.
2. Broadcasts the ledger entry to all participants.
3. Runs an Evaluator BT node to assign default roles (`[VENDOR]`).
4. Transforms the Offer into `Offer(CaseParticipant{actor=X, roles=[VENDOR]},
   Case)` addressed to the Case Owner, with `origin = original-offer-id`.

The Case Owner responds with `Accept(Offer)` or `Reject(Offer)` to the CaseActor.
The CaseActor records the response, fans it out, and either sends
`Invite(CaseStub+embargo)` to Actor X or sends `RejectActorRecommendation` to
the original recommender (with `in_reply_to = original-offer-id`).

- Good: all protocol events pass through the CaseActor and are recorded in the
  ledger.
- Good: the Case Owner can override default roles in their Accept response.
- Good: the recommender's original offer and the Case Owner's decision are both
  auditable.
- Good: the `origin` field on the CaseActor's Offer to the Case Owner preserves
  the causal chain without requiring a separate lookup table.
- Neutral: adds two extra protocol hops (recommender→CaseActor,
  CaseActor→CaseOwner) compared to Option A.

### Option C: Any-participant-can-invite

Any existing participant can directly invite another actor without Case Owner
approval.

- Good: simpler for cases with low-trust or egalitarian coordination styles.
- Bad: removes the ownership gate; violates CM-02-001 (Case Owner administers
  the case).
- Bad: in multi-vendor or multi-coordinator scenarios, uncontrolled invites
  create race conditions on participant list state.
- Rejected.

## Decision Outcome

Chosen option: **Option B — CaseActor-routed with transform**, because it is the
only option that satisfies all routing invariants (ADR-0021, PCR-08) and the
ledger recording requirement (CLP-07) while preserving the Case Owner as sole
decision-maker for participant membership.

### Consequences

- Good: the suggest-actor flow becomes consistent with all other case-scoped
  protocol messages.
- Good: all three roles in the flow — recommender, CaseActor, Case Owner — have
  a clearly defined inbox and single responsibility.
- Good: the `origin` field canonicalizes how AS2 activities carry causal chain
  context without a side-channel data store.
- Bad: the existing `suggest_actor_tree.py` BT and `suggest_actor_demo.py`
  must be redesigned; they cannot be incrementally adapted.
- Bad: the Case Owner now receives a transformed Offer (CaseParticipant) rather
  than the recommender's original Offer; implementations must handle the
  indirection.

### Ledger Commit Ordering

Per the invariant established in this design session: a ledger entry MUST be
committed only for events that have already occurred — receipt of an inbound
message or emission of an outbound message. Pre-committing a decision before
communicating it is not permitted. The sequence for every step in this flow is:
(1) send/receive the protocol message, (2) record it in the ledger, (3) fan-out
the ledger entry to all participants.

### Duplicate Recommendation Handling

Three distinct states must be distinguished when a second `Offer(Actor X)` arrives:

| State | CaseActor behavior |
|---|---|
| Pending decision (first Offer not yet resolved) | Record in ledger, fan-out, send Note to Case Owner noting the reinforcing demand signal |
| Invite issued to Actor X (awaiting Accept/Reject) | Record in ledger, fan-out, auto-send `AcceptActorRecommendation` to second recommender, no duplicate Invite |
| Actor X is already a participant | Record in ledger, fan-out, auto-send `AcceptActorRecommendation` to second recommender |

## Validation

- `suggest_actor_tree.py` and its test coverage must be rewritten to exercise
  the new CaseActor-side BT (receive `Offer(Actor)`, transform,
  forward `Offer(CaseParticipant)` to Case Owner).
- `suggest_actor_demo.py` must be updated to route the recommendation to the
  CaseActor inbox rather than the Case Owner inbox.
- A new received-side BT must handle `Accept(Offer(CaseParticipant))` from the
  Case Owner at the CaseActor and trigger `Invite(CaseStub+embargo)` to the
  invitee.
- Spec requirements CM-16 and CM-17 (in `specs/case-management.yaml`) capture
  the normative requirements derived from this decision.

## More Information

- ADR-0021: CaseActor Inbox Routing as the Sole Path to Canonical Ledger Entries
- ADR-0022: Single BT Execution Per Inbox Delivery for Received-Side CaseActor Routing
- `notes/case-communication-model.md` — canonical PCR-08 routing rules
- `notes/case-bootstrap-trust.md` — late-joiner trust establishment
- `specs/participant-case-replica.yaml` PCR-08 — invite/accept/bootstrap chain
- Issue #1292 — invite/embargo consent completeness epic
- Issue #1295 — tracking issue for this ADR + spec additions PR

Generated spec requirements: `case-management.yaml` CM-16, CM-17.
