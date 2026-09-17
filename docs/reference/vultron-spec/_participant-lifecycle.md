## 11. Participant Lifecycle Within a Case [N]

A case is not a fixed set of parties. Actors join, take on roles, hand
responsibilities to one another, and leave. This section specifies that lifecycle:
how an actor acquires a role, how it is brought into a case, how case ownership
moves, and what the protocol does and does not say about removal.

### 11.1 Role Assignment [N]

A role is granted through the case's authority chain. An actor does not acquire a
case role by declaring that it holds one, because the other participants act on
role claims: they send a Vendor the report content and treat a Coordinator's
routing decisions as authoritative. A self-declared role would let an actor take
on authority the Case Owner never granted.

1. A case begins with a **Case Owner** — the actor whose disclosure decision the
   case exists to serve. Case ownership is not delegated, though it may be
   transferred ([§11.3](index.md#113-case-ownership-transfer-n)).
2. The Case Owner MAY delegate the **Case Manager** role. The delegation is an
   `Offer(CaseParticipantRole)` addressed to the receiving actor in the context of
   the case, answered with `Accept` or `Reject`. The same activity grants any
   other role.
3. The Case Manager records each actor's roles on that actor's
   `CaseParticipant` entry in the case.

An actor MUST NOT be recorded as holding a role it did not accept, and a
participant MUST NOT be recorded as holding a role the Case Owner did not grant.
When an actor accepts a role offer, the roles it receives MUST be taken from the
offer the case sent, not from the accepting actor's reply — otherwise an actor
could widen its own grant on the way back.

An implementation MAY verify that an actor has the capability prerequisites for a
role ([§12.3.1](index.md#1231-process-roles)) before completing the assignment.

{% include-markdown "./_oq-role-acquisition.md" %}

### 11.2 Invitation and Acceptance [N]

Bringing a new actor into a case has a problem to solve: the actor cannot decide
whether to join until it knows something about the case, but it must not receive
case content before it has been admitted and its embargo consent resolved
([§9.7](index.md#97-gating-full-case-delivery)).

The protocol solves this with a **case stub** — a minimal description of the case
carrying enough for the invitee to decide, and no vulnerability detail. The stub
names the case, says who is coordinating it, and states the embargo terms the
invitee would be agreeing to. Full content follows only after the invitee accepts.

Two paths bring an actor into a case, and they differ in who initiates:

- **Direct invitation.** The CASE_MANAGER sends `Invite`, carrying the case stub,
  to the actor. The actor answers `Accept(Invite)` or `Reject(Invite)`.
  `Accept(Invite)` admits the actor at RM Received and, where an embargo is in
  force, records its consent to those terms.
- **Suggested actor.** An existing participant proposes a third party — "this
  vendor is also affected" — by sending `Offer(CaseParticipant)` to the
  CASE_MANAGER. The proposal is a recommendation, not an invitation: the Case
  Owner decides whether to act on it, and if it does, the CASE_MANAGER then sends
  the `Invite` above. An implementation MUST NOT treat
  `Offer(CaseParticipant)` as an invitation to the proposed actor.

Both paths converge on `Accept(Invite)`. The suggested-actor path adds one
round-trip, because the Case Owner's decision sits between the proposal and the
invitation.

!!! note "Recall: report management states"
    {% include-markdown "./includes/_rm-states-table.md" %}

    Full definitions are in [§6.1](index.md#61-states).

### 11.3 Case Ownership Transfer [N]

The Case Owner MAY transfer ownership to another actor via
`Offer(VulnerabilityCase)` / `Accept` handshake routed through the CASE_MANAGER
(ADR-0053). On acceptance, the receiving actor acquires Case Owner authority and
the associated protocol responsibilities.

!!! note "Open: cryptographic identity across a change of case manager"
    Authority over the canonical ledger follows the `CASE_MANAGER` role, not any
    actor's name or URI. Transferring case ownership, or moving the
    `CASE_MANAGER` role to a different actor, therefore does not by itself
    re-key the ledger.

    What remains open is key handover. A future case-encryption design must
    define how the keys protecting existing case content pass to the new role
    holder, and what a participant does with ledger entries it can no longer
    decrypt. This specification states no rule for either.

### 11.4 Participant Removal [I]

A Case Owner or Case Manager MAY remove a participant from a case.
The protocol mechanics of removal and the effect on active embargo consent
are not yet fully specified.

!!! info "See also"
    - [Transferring a Case](../../howto/activitypub/activities/transfer_ownership.md)
    - [Role Delegation](../../howto/activitypub/activities/role_delegation.md)
    - [Suggest an Actor for a Case](../../howto/activitypub/activities/suggest_actor.md)

---
