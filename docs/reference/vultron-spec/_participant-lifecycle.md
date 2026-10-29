## 12. Participant Lifecycle Within a Case [N]

A case is not a fixed set of parties. Actors join, take on roles, hand
responsibilities to one another, and leave. This section specifies that lifecycle:
how an actor acquires a role, how it is brought into a case, how case ownership
moves, and how a participant is removed.

### 12.1 Role Assignment [N]

A role is granted through the case's authority chain.
An actor does not acquire a case role by declaring that it holds one.
The reason is that the other participants act on role claims.
They send a Vendor the report content and treat a Coordinator's routing decisions as authoritative.
A self-declared role would let an actor take on authority the Case Owner never granted.

1. A case begins with a **Case Owner** — the actor whose disclosure decision the
   case exists to serve. Case ownership is not delegated, though it can be
   transferred ([§12.3 Case Ownership Transfer](interactions.md#123-case-ownership-transfer-n)).
2. The Case Owner can offer an additional role to an actor that is already a participant.
   The offer is an `Offer(CaseParticipantRole)` addressed to the case's Case Manager only, never to the receiving actor.
   The Case Manager records the offer and forwards it to the receiving actor, which answers the Case Manager with `Accept` or `Reject`.
   The Case Manager records the answer and grants the role on an `Accept`.
   The Case Owner makes role offers.
   A Case Manager whose policy delegates role offers to it can also make one, under the same checks.
   The Case Owner and Case Manager roles cannot be offered.
   Ownership moves by transfer.
   How the Case Manager role is handed to another actor is not yet specified.
3. The Case Manager records each actor's roles on that actor's
   `CaseParticipant` entry in the case.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-33-001", "CM-33-002", "CM-33-003", "CM-33-004", "CM-33-005", "CM-33-006"))
```

Together these rules mean that an actor holds only a role it accepted, from an offer that the Case Owner made, or that a Case Manager made where its policy delegates role offers to it.
The role an `Accept` grants is the one the recorded offer names, not one the accepting actor's reply names.
Otherwise, an actor could widen its own grant on the way back.
An invitee's roles are those its stub Invite names, recorded when the Case Manager sends that Invite ([§12.2 Invitation and Acceptance](interactions.md#122-invitation-and-acceptance-n)).

An implementation can check that an actor has the capability prerequisites for a
role ([§13.3.1 Process Roles](conformance.md#1331-process-roles)) before completing the assignment.

{% include-markdown "./_oq-role-acquisition.md" %}

### 12.2 Invitation and Acceptance [N]

Bringing a new actor into a case has a problem to solve.
The actor cannot decide whether to join until it knows something about the case.
However, until it is an active participant it receives no case content.
Being in the case's participant list does not make it one ([§9.7 Gating Full Case Delivery](tracking-models.md#97-gating-full-case-delivery)).

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-10-004", "CM-17-005"))
```

The protocol solves this with a **case stub**: a minimal stand-in for the case that carries enough for the invitee to decide, and no vulnerability detail.
The stub is its own object, of type `VulnerabilityCaseStub`, and is not the case.
It carries exactly these fields:

- `id`: the stub's own identifier, which is the case's identifier with `/stub` appended.
  A receiver never derives the case from it.
- `type`: `VulnerabilityCaseStub`.
  A receiver tells a stub from a case by its `type` alone.
- `caseId`: the identifier of the case the stub stands for.
- `activeEmbargo` and `caseStatus`: present whenever an embargo is in force, that is, while the embargo state is `ACTIVE` or `REVISE`.
  They state the embargo terms the invitee would agree to by accepting: the embargo in force and the case's embargo state.
  During a revision the stub carries the embargo in force, never the open revision, which the invitee receives after joining.
  The stub may carry the embargo inline or name it by an identifier the invitee can ask the inviter to resolve.
  The reference implementation always carries the full embargo inline, because it does not build that lookup.
- `summary`: required human-readable context saying what the invitee is being asked to join.
  The sender chooses it.
  It may be the case name, or a deliberately less revealing string.
  The case name itself can be sensitive to share with an actor not yet bound by the embargo.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-11-013", "CM-17-010", "CM-17-002", "EP-09-011", "MV-10-001"))
```

The stub does not name the case's coordinator or Case Owner.
The `Invite` that carries the stub already identifies who is asking: its `actor` is the CASE_MANAGER, and its `attributedTo` can name the Case Owner.
Full content follows only after the invitee accepts.

Two paths bring an actor into a case, and they differ in who initiates.

**Direct invitation.**
The CASE_MANAGER sends `Invite(Actor)[target=VulnerabilityCaseStub]` to the actor.
At the same time, it records the invitee in the case as an *inert* participant at RM Received.
The CASE_MANAGER commits the record's creation to the case ledger, and a replica applying that entry creates the same inert record.
The record is not yet an active participant: it does not receive case content and is not included in embargo fan-out.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-11-006"))
```

The actor answers `Accept(Invite)` or `Reject(Invite)`.
`Accept(Invite)` joins the actor to the case at RM Received and, where an embargo is in force, records its consent to those terms, unless it had already declined them.
A participant that has now agreed to the embargo in force, or joins a case with none, is active, and the CASE_MANAGER delivers the case ([§11.1 Admitting a Participant](interactions.md#111-admitting-a-participant)).
A participant that had declined the embargo joins but stays inert until it agrees.
`Reject(Invite)` closes the inert record (RM Received → Closed) and keeps it as history, so the CASE_MANAGER can see that the invitation was extended and declined.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-11-001", "CM-11-007"))
```

Every stub Invite carries a reply deadline.
When it passes unanswered, the Invite closes as expired and the record is left unchanged: still inert, at RM Received, with its embargo consent row still `INVITED`.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-11-014"))
```

After joining, the participant judges the case by answering the full-case Invite, not the original report Offer.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-11-011", "CM-11-020"))
```

**Suggested actor.**
An existing participant proposes a third party — "this vendor is also affected" — by sending `Offer(Actor)[target=VulnerabilityCase]` to the CASE_MANAGER.
The CASE_MANAGER records the suggestion and passes it to the Case Owner as `Offer(CaseParticipant)[target=VulnerabilityCase]`.
The suggestion is a recommendation, not an invitation: the Case Owner decides whether to act on it.
If the Case Owner accepts, the CASE_MANAGER then sends the stub `Invite` above.
The CASE_MANAGER takes the actor to invite and its roles from the offer it recorded, never from the Case Owner's reply.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-16-001", "CM-16-004", "CM-16-006", "CM-16-018", "CM-16-019"))
```

Both paths converge on `Accept(Invite)`.
The suggested-actor path adds one round-trip, because the Case Owner's decision sits between the proposal and the invitation.

!!! note "Recall: report management states"
    {% include-markdown "./includes/_rm-states-table.md" %}

    Full definitions are in [§6.1 States](tracking-models.md#61-states).

### 12.3 Case Ownership Transfer [N]

The Case Owner can transfer ownership to another participant through an
`Offer(VulnerabilityCase)` / `Accept` handshake routed through the CASE_MANAGER.
The Case Owner proposes the transfer to the CASE_MANAGER as `Offer(Offer(VulnerabilityCase))`, and the CASE_MANAGER makes the one `Offer(VulnerabilityCase)` the receiving actor answers.
The receiving actor is one already entitled to the case's content and holding the case, which the Offer names by reference: an active participant.
An owner that means to transfer a case to any other actor invites that actor first.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-21-005", "CM-21-021"))
```

On acceptance, the receiving actor acquires Case Owner authority and
the associated protocol responsibilities.
The previous owner loses the Case Owner role, and keeps its other roles and its place in the case.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-21-011", "CM-21-002", "CM-21-003", "CM-21-008", "CM-21-009"))
```

!!! note "Open: cryptographic identity across a change of case manager"
    Authority over the canonical ledger follows the `CASE_MANAGER` role, not any
    actor's name or Uniform Resource Identifier (URI). Transferring case ownership, or moving the
    `CASE_MANAGER` role to a different actor, therefore does not by itself
    re-key the ledger.

    What remains open is key handover.
    A future case-encryption design needs to define how the keys protecting existing case content pass to the new role holder.
    It also needs to define what a participant does with ledger entries it can no longer decrypt.
    This specification states no rule for either.

### 12.4 Participant Removal [N]

Removing a participant withdraws its entitlement to case content.
It does not delete the participant from the case.
The participant's record, its status history, and the ledger entries it authored stay in the case, and the record carries a removal fact.
A removed participant is inert: it receives no case content, and it has no authority to act on the case.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-31-001"))
```

Only the Case Owner requests a removal.
It sends `Remove(CaseParticipant)[target=VulnerabilityCase]` to the CASE_MANAGER, which applies it.
The CASE_MANAGER refuses the request in each of these cases:

- the sender does not hold the Case Owner role;
- the request names the CASE_MANAGER's or the Case Owner's participant;
- the request names no participant of the case.

A second removal of an already-removed participant is a no-op, and the CASE_MANAGER reports it as skipped.
The CASE_MANAGER never removes a participant on its own initiative.
A participant that wants to stop taking part leaves the case with `Leave(VulnerabilityCase)`; that is not removal.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-31-004"))
```

An accepted removal is one ledger entry: the Case Owner's received `Remove(CaseParticipant)`, committed by the CASE_MANAGER as received.
The CASE_MANAGER commits no second entry of its own for the same removal.
After the commit, the CASE_MANAGER sends the removed participant a direct `Remove(CaseParticipant)` that names it.
The notice has `actor` set to the CASE_MANAGER and `attributedTo` set to the Case Owner.
This notice is delivery, not a record, and is not ledgered.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-31-005", "CM-31-006"))
```

The removal entry's fan-out selects its recipients before the removal is applied, so the removed participant receives that entry too.
It is the last ledger entry the removed participant receives, by fan-out or by replay, until it is reinstated.
Every replica, the removed participant's own included, applies the removal from that ledger entry.
A replica never applies a removal from a directly received `Remove(CaseParticipant)`: it stores the notice and takes the removal from the ledger.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-31-007"))
```

Removal does not change the participant's embargo consent.
A removed signatory stays bound by the embargo it accepted.
A removed participant receives no Invite of any kind: not a stub Invite, not a full-case Invite, and not an embargo Invite.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-31-008", "CM-31-013"))
```

Removal is reversible.
The Case Owner reinstates a removed participant by sending `Add(CaseParticipant)[target=VulnerabilityCase]` to the CASE_MANAGER.
The request follows the removal pipeline:

- only the Case Owner may send it;
- the received `Add` is the one ledger entry;
- the CASE_MANAGER sends the participant a direct `Add(CaseParticipant)` notice that names it;
- every replica applies the reinstatement from the ledger entry.

Reinstatement clears the removal fact.
The participant does not accept again, because it never withdrew.

The CASE_MANAGER refuses an `Add` that names a participant that is not removed or that never joined the case.
`Add` does not seat a new member, and an actor joins only by accepting its stub Invite.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-31-011"))
```

For the same reason, the CASE_MANAGER does not send `Add(CaseParticipant)` when an invitee accepts its stub Invite.
The ledger holds the messages exchanged: the Invite, the CASE_MANAGER's creation of the inert record, then the invitee's Accept.
That Accept is the entry for the invitee's consent and `joined` mark.
Every replica applies what the entries carry.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-31-012"))
```

When the reinstated participant is active again, the CASE_MANAGER sends it every ledger entry committed after its removal entry, in log order.
Its copy of the ledger then joins the chain with no gap.
A participant reinstated into a case whose active embargo it has not accepted stays inert.
The CASE_MANAGER sends it that embargo's Invite, and its catch-up waits until it accepts.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-10-006"))
```

!!! info "See also"
    - [Transferring a Case](../../topics/case_lifecycle/ownership_transfer.md)
    - [How to Delegate a Role to Another Participant](../../howto/activitypub/activities/role_delegation.md)
    - [How to Suggest an Actor for a Case](../../howto/activitypub/activities/suggest_actor.md)

---
