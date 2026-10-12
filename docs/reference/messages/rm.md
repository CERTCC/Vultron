---
stakeholder_type: [platform-developer]
level: 400
description: >
  Wire activities for the Report Management message types RS, RI, RV, RD, RA, RC, RK, and RE.
---

# Report Management (RM) Messages

The RM shorthands inform other Participants of the sender's report-handling
state. Receipt of a *Report Submission* is the only RM message whose receipt
directly triggers an RM state change in the receiver; all others convey the
sender's status.

The RM state ladder has **two** wire expressions: the dedicated report-scoped
activities listed below, and the `rm_state` field of an
`Add(ParticipantStatus)` broadcast (see [Case State (CS)](cs.md)). *Report/Case
Accepted* (`RA`) and *Report/Case Deferred* (`RD`) additionally take case-scoped
verbs — `Join(VulnerabilityCase)` and `Ignore(VulnerabilityCase)` — because
engaging or deferring is a case-participation decision rather than a
report-validity judgment (MSM-01-004, MSM-01-005).

The CASE_MANAGER applies one rule to an RM state whichever of these expressions carries it (RSH-06-006).
The state is recorded for the sender, never for the receiver (RSH-08-001), and only when the sender is a participant of the case.
A forward move is recorded even when it skips states, and the CASE_MANAGER then asks the sender in a note which path it took (RSH-06-001, RSH-06-004).
A backward move is refused and the recorded state stands (RSH-06-002), and the CASE_MANAGER tells the sender in a note that it refused the move (RSH-06-004).
An activity and an `Add(ParticipantStatus)` that report the same move record it once (RSH-08-002).

## Occasions

{% include-markdown "./_occasions/lookup-rm.md" %}

{% include-markdown "./_occasions/sections/create-report.md" %}

- **Triggering transition:** none (object construction, not a state change).

{% include-markdown "./_occasions/sections/report-submission.md" %}

- **Triggering transition:** emitted when the sender is Accepted (sender ∈ A).
- **Receiver:** the receiver does not refuse a new report on the sender's standing; it acts only when it is in the Offer's `to` (HP-01-010, HP-09-001).
- **Proposed embargo terms:** the Offer may carry `proposedEmbargo`, an inline `EmbargoEvent` whose `context` is the report; the case owner compares it with its own default at case creation and the shorter wins (EP-04-003, EP-04-004).

{% include-markdown "./_occasions/sections/report-acknowledgment.md" %}

- **Triggering transition:** any valid RM message.
- **Object:** the report's original `Offer`, not the report itself; a bare `Read(VulnerabilityReport)` matches no pattern.
  `RK` survives as a dedicated wire activity because report submission is not ledger-replicated (MSM-01-008).

{% include-markdown "./_occasions/sections/report-valid.md" %}

- **Triggering transition:** Received or Invalid → Valid ({R,I} → V).
- **Second wire form:** a participant that joined through an Invite sends `Accept(Invite(Actor, target=VulnerabilityCase))` instead, answering the full-case Invite ([VAM-04-012](../specs/protocol.md#vam-04-012)); see [Accept Full-Case Invite](case_management.md#accept-full-case-invite).
  It never validates the original report Offer ([CM-11-020](../specs/protocol.md#cm-11-020)).

{% include-markdown "./_occasions/sections/report-invalid.md" %}

- **Triggering transition:** Received → Invalid (R → I).
- **Second wire form:** a participant that joined through an Invite sends `TentativeReject(Invite(Actor, target=VulnerabilityCase))` instead, answering the full-case Invite ([VAM-04-013](../specs/protocol.md#vam-04-013)); see [Tentatively reject Full-Case Invite](case_management.md#tentatively-reject-full-case-invite).

{% include-markdown "./_occasions/sections/report-closed.md" %}

- **Triggering transition:** Received, Invalid, Deferred, or Accepted → Closed ({R,I,D,A} → C).
- **Second wire form:** a participant that joined through an Invite closes with `Reject(Invite(Actor, target=VulnerabilityCase))` ([VAM-04-014](../specs/protocol.md#vam-04-014)); see [Reject Full-Case Invite](case_management.md#reject-full-case-invite).
  An invitee that declines its stub Invite sends `Reject(Invite(Actor, target=VulnerabilityCaseStub))` ([CM-11-007](../specs/protocol.md#cm-11-007)); see [Reject invite to case](case_management.md#reject-invite-to-case).
- **Fault axis:** the `Reject(Offer(VulnerabilityReport))` activity also appears as an ordinary refusal in the fault-and-acknowledgment mapping (MSM-05-003); see [Faults and Acknowledgments](faults_and_acknowledgements.md#asreject-is-overloaded).

{% include-markdown "./_occasions/sections/report-accepted.md" %}

- **Triggering transition:** Valid or Deferred → Accepted ({V,D} → A).
- **Re-engagement:** re-engaging a deferred case emits the same activity.
  There is no separate re-engagement wire form, because `DEFERRED` → `ACCEPTED` is a forward transition rather than a retraction of the earlier deferral.

{% include-markdown "./_occasions/sections/report-deferred.md" %}

- **Triggering transition:** Valid or Accepted → Deferred ({V,A} → D).
- **Why a case verb:** deferring is a case-participation decision, not a report-validity judgment (MSM-01-004).

## Formal messages with no dedicated wire activity

### RE — Report Error

- **Protocol role:** Indicates a Participant received an unexpected RM message.
- **Triggering transition:** any unexpected RM message.
- **Wire activity:** none dedicated. Faults are conveyed by
  `Create(ProcessingFault)` (not understood), `as:Reject` (understood but
  declined), or `Create(Note)` (needing explanation), partitioned by failure
  mode rather than by state machine
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#rm-message-types).
