## 11. Participant Lifecycle Within a Case [N]

A case is not a fixed set of parties. Actors join, take on roles, hand
responsibilities to one another, and leave. This section specifies that lifecycle:
how an actor acquires a role, how it is brought into a case, how case ownership
moves, and how a participant is removed.

### 11.1 Role Assignment [N]

A role is granted through the case's authority chain. An actor does not acquire a
case role by declaring that it holds one, because the other participants act on
role claims: they send a Vendor the report content and treat a Coordinator's
routing decisions as authoritative. A self-declared role would let an actor take
on authority the Case Owner never granted.

1. A case begins with a **Case Owner** — the actor whose disclosure decision the
   case exists to serve. Case ownership is not delegated, though it may be
   transferred ([§11.3 Case Ownership Transfer](interactions.md#113-case-ownership-transfer-n)).
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
role ([§12.3.1 Process Roles](conformance.md#1231-process-roles)) before completing the assignment.

{% include-markdown "./_oq-role-acquisition.md" %}

### 11.2 Invitation and Acceptance [N]

Bringing a new actor into a case has a problem to solve: the actor cannot decide
whether to join until it knows something about the case, but it must not receive
case content before it has been admitted and its embargo consent resolved
([§9.7 Gating Full Case Delivery](tracking-models.md#97-gating-full-case-delivery)).

The protocol solves this with a **case stub**: a minimal stand-in for the case that carries enough for the invitee to decide, and no vulnerability detail.
The stub is its own object, of type `VulnerabilityCaseStub`, and is not the case ([CM-11-013](../specs/protocol.md#cm-11-013)).
It carries exactly these fields ([CM-17-010](../specs/protocol.md#cm-17-010)):

- `id`: the stub's own identifier, which is the case's identifier with `/stub` appended.
  A receiver never derives the case from it.
- `type`: `VulnerabilityCaseStub`.
  A receiver tells a stub from a case by its `type` alone.
- `caseId`: the identifier of the case the stub stands for.
- `activeEmbargo` and `caseStatus`: present only when an embargo is active.
  They state the embargo terms the invitee would agree to by accepting: the embargo's identifier and end time, and the case's embargo state ([CM-17-002](../specs/protocol.md#cm-17-002)).
- `summary`: required human-readable context saying what the invitee is being asked to join ([MV-10-001](../specs/protocol.md#mv-10-001)).
  The sender chooses it: it may be the case name, or a deliberately less revealing string, because the case name itself can be sensitive to share with an actor not yet bound by the embargo.

The stub does not name the case's coordinator or Case Owner.
The `Invite` that carries the stub already identifies who is asking: its `actor` is the CASE_MANAGER, and its `attributedTo` can name the Case Owner.
Full content follows only after the invitee accepts.

Two paths bring an actor into a case, and they differ in who initiates:

- **Direct invitation.** The CASE_MANAGER sends `Invite(Actor, target=VulnerabilityCaseStub)` to the actor.
  At the same time, it records the invitee in the case as an *inert* participant at RM Received ([CM-11-006](../specs/protocol.md#cm-11-006)).
  The CASE_MANAGER commits the record's creation to the case ledger, and a replica applying that entry creates the same inert record.
  The record is not yet an active participant: it does not receive case content and is not included in embargo fan-out until the actor accepts ([CM-10-004](../specs/protocol.md#cm-10-004)).
  The actor answers `Accept(Invite)` or `Reject(Invite)`.
  `Accept(Invite)` activates the inert record, admitting the actor at RM Received and, where an embargo is in force, recording its consent to those terms.
  `Reject(Invite)` closes the inert record (RM Received → Closed) and keeps it as history, so the CASE_MANAGER can see that the invitation was extended and declined ([CM-11-007](../specs/protocol.md#cm-11-007)).
  Every stub Invite carries a reply deadline.
  When it passes unanswered, the Invite closes as expired and the record is left unchanged: still inert, at RM Received, with its embargo consent row still `INVITED` ([CM-11-014](../specs/protocol.md#cm-11-014)).
  After joining, the participant judges the case by answering the full-case Invite, not the original report Offer ([CM-11-011](../specs/protocol.md#cm-11-011), [CM-11-020](../specs/protocol.md#cm-11-020)).
- **Suggested actor.** An existing participant proposes a third party — "this vendor is also affected" — by sending `Offer(CaseParticipant)` to the CASE_MANAGER.
  The proposal is a recommendation, not an invitation: the Case Owner decides whether to act on it, and if it does, the CASE_MANAGER then sends the `Invite` above.
  An implementation MUST NOT treat `Offer(CaseParticipant)` as an invitation to the proposed actor.

Both paths converge on `Accept(Invite)`.
The suggested-actor path adds one round-trip, because the Case Owner's decision sits between the proposal and the invitation.

!!! note "Recall: report management states"
    {% include-markdown "./includes/_rm-states-table.md" %}

    Full definitions are in [§6.1 States](tracking-models.md#61-states).

### 11.3 Case Ownership Transfer [N]

The Case Owner MAY transfer ownership to another actor via
`Offer(VulnerabilityCase)` / `Accept` handshake routed through the CASE_MANAGER
(ADR-0053). On acceptance, the receiving actor acquires Case Owner authority and
the associated protocol responsibilities.

!!! note "Open: cryptographic identity across a change of case manager"
    Authority over the canonical ledger follows the `CASE_MANAGER` role, not any
    actor's name or Uniform Resource Identifier (URI). Transferring case ownership, or moving the
    `CASE_MANAGER` role to a different actor, therefore does not by itself
    re-key the ledger.

    What remains open is key handover. A future case-encryption design must
    define how the keys protecting existing case content pass to the new role
    holder, and what a participant does with ledger entries it can no longer
    decrypt. This specification states no rule for either.

### 11.4 Participant Removal [N]

Removing a participant withdraws its entitlement to case content.
It does not delete the participant from the case.
The participant's record, its status history, and the ledger entries it authored stay in the case, and the record carries a removal fact ([CM-31-001](../specs/protocol.md#cm-31-001)).
A removed participant is inert: it receives no case content, and it has no authority to act on the case.

Only the Case Owner requests a removal.
It sends `Remove(CaseParticipant, target=VulnerabilityCase)` to the CASE_MANAGER, which applies it ([CM-31-004](../specs/protocol.md#cm-31-004)).
The CASE_MANAGER MUST refuse the request when the sender does not hold the Case Owner role, when it names the CASE_MANAGER's or the Case Owner's participant, or when it names no participant of the case.
A second removal of an already-removed participant is a no-op, and the CASE_MANAGER reports it as skipped.
The CASE_MANAGER MUST NOT remove a participant on its own initiative.
A participant that wants to stop taking part leaves the case with `Leave(VulnerabilityCase)`; that is not removal.

An accepted removal is one ledger entry: the Case Owner's received `Remove(CaseParticipant)`, committed by the CASE_MANAGER as received ([CM-31-005](../specs/protocol.md#cm-31-005)).
The CASE_MANAGER commits no second entry of its own for the same removal.
After the commit, the CASE_MANAGER sends the removed participant a direct `Remove(CaseParticipant)` that names it, with `actor` set to the CASE_MANAGER and `attributedTo` set to the Case Owner ([CM-31-006](../specs/protocol.md#cm-31-006)).
This notice is delivery, not a record, and is not ledgered.

The removal entry's fan-out selects its recipients before the removal is applied, so the removed participant receives that entry too.
It is the last ledger entry the removed participant receives, by fan-out or by replay, until it is reinstated.
Every replica, the removed participant's own included, applies the removal from that ledger entry ([CM-31-007](../specs/protocol.md#cm-31-007)).
A replica MUST NOT apply a removal from a directly received `Remove(CaseParticipant)`: it stores the notice and takes the removal from the ledger.

Removal does not change the participant's embargo consent ([CM-31-008](../specs/protocol.md#cm-31-008)).
A removed signatory stays bound by the embargo it accepted.
A removed participant receives no Invite of any kind: not a stub Invite, not a full-case Invite, and not an embargo Invite ([CM-31-013](../specs/protocol.md#cm-31-013)).

Removal is reversible.
The Case Owner reinstates a removed participant by sending `Add(CaseParticipant, target=VulnerabilityCase)` to the CASE_MANAGER ([CM-31-011](../specs/protocol.md#cm-31-011)).
The request follows the removal pipeline: only the Case Owner may send it, the received `Add` is the one ledger entry, the CASE_MANAGER sends the participant a direct `Add(CaseParticipant)` notice naming it, and every replica applies the reinstatement from the ledger entry.
Reinstatement clears the removal fact.
The participant does not accept again, because it never withdrew.
The CASE_MANAGER MUST refuse an `Add` that names a participant that is not removed or that never joined the case: `Add` does not seat a new member, and an actor joins only by accepting its stub Invite.
For the same reason the CASE_MANAGER does not send `Add(CaseParticipant)` when an invitee accepts its stub Invite; every replica creates the inert record from the stub Invite's ledger entry and marks it joined from the `Accept(Invite)` entry ([CM-31-012](../specs/protocol.md#cm-31-012)).

When the reinstated participant is active again, the CASE_MANAGER sends it every ledger entry committed after its removal entry, in log order, so its copy of the ledger joins the chain with no gap ([CM-10-006](../specs/protocol.md#cm-10-006)).
A participant reinstated into a case whose active embargo it has not accepted stays inert.
The CASE_MANAGER sends it that embargo's Invite, and its catch-up waits until it accepts.

!!! info "See also"
    - [Transferring a Case](../../topics/case_lifecycle/ownership_transfer.md)
    - [How to Delegate a Role to Another Participant](../../howto/activitypub/activities/role_delegation.md)
    - [How to Suggest an Actor for a Case](../../howto/activitypub/activities/suggest_actor.md)

---
