---
stakeholder_type: [platform-developer, project-contributor]
level: 400
description: >
  Case lifecycle, participant roster, and ownership transfer activities.
---

# Case Management Messages

These messages drive the lifecycle of a `VulnerabilityCase` and its roster of
participants. They have no formal-protocol shorthand — the 28-symbol formal
message set addresses state-machine transitions, not the case-infrastructure
layer that supports them (see
[ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).

All messages on this page operate on a case that already exists. For the
pre-existence bootstrap (vendor → case-actor service) see
[Case Proposal](case_proposal.md). For the ledger mechanism that replicates
these activities to all participants see
[Ledger Replication](ledger_replication.md).

Two authorities appear below, and they are distinct roles rather than one actor.
The **Case Owner** decides for the case: who is admitted, which roles they hold, and whether an ownership transfer is offered.
The **CASE_MANAGER** is the case's single-writer authority: it mints and updates the `VulnerabilityCase` object, records every case-scoped message in the ledger, and delivers case snapshots to participants (spec [§5.4.1 Single-Writer Authority](../vultron-spec/layers.md#541-single-writer-authority), [ADR-0088](../../adr/0088-consolidate-case-authority-determination.md)).
The CASE_MANAGER acts on the Case Owner's behalf; the two roles are often held by the same actor but need not be.
The 300-level introduction is [The Case Manager and the Case Ledger](../../topics/case_lifecycle/case_manager_and_ledger.md).

## Message mapping

```python exec="true" idprefix=""
from vultron.metadata.msm.render import render_page

print(render_page("case_management", heading=False))
```

---

## Create Case

- **Protocol role:** The CASE_MANAGER mints a new `VulnerabilityCase`, seats the initial participants (the Case Owner and the reporter), and links the report, then sends the completed case once to the report submitter as the trust bootstrap (spec [§4.5 Trust and Bootstrap Semantics](../vultron-spec/layers.md#45-trust-and-bootstrap-semantics); [CBT-01-001](../specs/protocol.md#cbt-01-001), [CM-22-002](../specs/protocol.md#cm-22-002)).
- **Who is named where:** the `actor` of the `Create` is the CASE_MANAGER that mints the case, and the case's `attributedTo` is the Case Owner ([CP-09-001](../specs/protocol.md#cp-09-001), [CM-02-008](../specs/protocol.md#cm-02-008)).
  The two coincide when the Case Owner creates its own case, as in the example below.
  When a case-actor service creates the case from a [Case Proposal](case_proposal.md), the service is the `actor` and `attributedTo` names the proposing actor, never the service itself.
  Every owner check reads `attributedTo`, and an ownership transfer rewrites it ([CM-21-002](../specs/protocol.md#cm-21-002)).
- **Triggering transition:** none — object construction precedes protocol state.
- **Wire activity:** `Create(VulnerabilityCase)`.
- **Example artifact:** [create_case.json](../examples/create_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_case, json2md

print(json2md(create_case()))
```

---

## Update Case

- **Protocol role:** The CASE_MANAGER records a changed `VulnerabilityCase` object — for example after a title edit or an ownership transfer is applied — and fans it out through the ledger ([§5.4.2 Routing Topology](../vultron-spec/layers.md#542-routing-topology)).
  A participant that wants a change made asks the CASE_MANAGER; it does not send `Update` to its peers.
- **Triggering transition:** none — metadata change, not a state transition.
- **Wire activity:** `Update(VulnerabilityCase)`.
- **Example artifact:** [update_case.json](../examples/update_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import update_case, json2md

print(json2md(update_case()))
```

---

## Add Report to Case

- **Protocol role:** Links a `VulnerabilityReport` to an existing case.
- **Triggering transition:** none — a report can be added at any RM state.
- **Wire activity:** `Add(VulnerabilityReport)` with `target` = case URI.
- **Who may send:**
  The CASE_MANAGER accepts it only from the Case Owner, and a participant replica accepts it only from the CASE_MANAGER.
  Any other sender is refused and the report is not attached.
- **Example artifact:** [add_report_to_case.json](../examples/add_report_to_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_report_to_case, json2md

print(json2md(add_report_to_case()))
```

---

## Close Case

- **Protocol role:** The sender signals that their participation in the case
  is complete (RM Accepted → Closed).
- **Triggering transition:** RM: A → C.
- **Wire activity:** `Leave(VulnerabilityCase)`.
- **Example artifact:** [close_case.json](../examples/close_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import close_case, json2md

print(json2md(close_case()))
```

---

## Offer Case Participant Role

- **Protocol role:** An authorized participant offers a specific `CVDRole` on the case to another actor.
  The object type alone identifies the activity as a role offer rather than an ownership-transfer offer (ADR-0039).
  Roles are granted through the case's authority chain ([§11.1 Role Assignment](../vultron-spec/interactions.md#111-role-assignment-n)).
- **Triggering transition:** none — roster action, not a state-machine event.
- **Wire activity:** `Offer(CaseParticipantRole)`, with `target` = the Actor
  receiving the role and `context` = the case.
- **How-to:** [How to Delegate a Role to Another Participant](../../howto/activitypub/activities/role_delegation.md).
- **Example artifact:** [offer_case_participant_role.json](../examples/offer_case_participant_role.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import offer_case_participant_role, json2md

print(json2md(offer_case_participant_role()))
```

The [`CaseParticipantRole`](../activitypub/objects.md#caseparticipantrole) object carries the role. This offer is distinct from
`Offer(CaseParticipant)`, which forwards an actor recommendation to the Case Owner
and is covered on [General (GI) Messages](general.md).

---

## Accept Case Participant Role

- **Protocol role:** The target actor accepts the offered role and holds it from
  that point.
- **Triggering transition:** none — roster action.
- **Wire activity:** `Accept(Offer(CaseParticipantRole))`.
- **How-to:** [How to Delegate a Role to Another Participant](../../howto/activitypub/activities/role_delegation.md).
- **Example artifact:** [accept_case_participant_role.json](../examples/accept_case_participant_role.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import accept_case_participant_role, json2md

print(json2md(accept_case_participant_role()))
```

---

## Reject Case Participant Role

- **Protocol role:** The target actor declines the offered role. The roster is
  unchanged.
- **Triggering transition:** none — roster action.
- **Wire activity:** `Reject(Offer(CaseParticipantRole))`.
- **How-to:** [How to Delegate a Role to Another Participant](../../howto/activitypub/activities/role_delegation.md).
- **Example artifact:** [reject_case_participant_role.json](../examples/reject_case_participant_role.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import reject_case_participant_role, json2md

print(json2md(reject_case_participant_role()))
```

The dedicated object type is preferred over a `target`-field discriminator ([SE-08-003](../specs/protocol.md#se-08-003)), and the earlier wire format `Offer(VulnerabilityCase, target=CaseParticipant)` for offering a role has been removed.

---

## Offer Case Ownership Transfer

- **Protocol role:** The current Case Owner offers to transfer ownership to another actor (e.g. from a reporter to a coordinator).
  The offer is routed through the CASE_MANAGER, which records it in the ledger ([§11.3 Case Ownership Transfer](../vultron-spec/interactions.md#113-case-ownership-transfer-n)); see [Case Ownership Transfer](../../topics/case_lifecycle/ownership_transfer.md).
- **Triggering transition:** none — ownership transfer is a roster operation.
- **Wire activity:** `Offer(VulnerabilityCase)` with `target` = recipient URI.
- **Example artifact:** [offer_case_ownership_transfer.json](../examples/offer_case_ownership_transfer.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import offer_case_ownership_transfer, json2md

print(json2md(offer_case_ownership_transfer()))
```

---

## Accept Case Ownership Transfer

- **Protocol role:** The recipient accepts the ownership transfer offer.
- **Triggering transition:** none — roster operation.
- **Wire activity:** `Accept(Offer(VulnerabilityCase))`.
- **Example artifact:** [accept_case_ownership_transfer.json](../examples/accept_case_ownership_transfer.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import accept_case_ownership_transfer, json2md

print(json2md(accept_case_ownership_transfer()))
```

---

## Reject Case Ownership Transfer

- **Protocol role:** The recipient declines the ownership transfer offer.
- **Triggering transition:** none — roster operation.
- **Wire activity:** `Reject(Offer(VulnerabilityCase))`.
- **Example artifact:** [reject_case_ownership_transfer.json](../examples/reject_case_ownership_transfer.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import reject_case_ownership_transfer, json2md

print(json2md(reject_case_ownership_transfer()))
```

---

## Invite Actor to Case

- **Protocol role:** The CASE_MANAGER invites a new actor to join the case, carrying the case stub and the embargo terms the invitee would agree to.
  The Case Owner decides whom to invite; a participant that wants a third party brought in sends a recommendation instead (`Offer(CaseParticipant)`, on [General (GI) Messages](general.md)).
  See [§11.2 Invitation and Acceptance](../vultron-spec/interactions.md#112-invitation-and-acceptance-n).
- **Triggering transition:** none — roster action.
- **Wire activity:** `Invite(Actor, target=VulnerabilityCaseStub)`.
  The `object` is the actor being invited, and the `target` is the case stub, of type `VulnerabilityCaseStub`.
  The stub carries the case identifier in its `caseId` and a required `summary` field: the owner-chosen description the invitee reads before deciding whether to accept ([CM-11-013](../specs/protocol.md#cm-11-013), [CM-17-010](../specs/protocol.md#cm-17-010), [MV-10-001](../specs/protocol.md#mv-10-001)).
  The factory raises `VultronActivityConstructionError` when `VulnerabilityCase.stub_summary` is not set, and the receiver refuses a stub with an absent or blank `summary`.
  The Invite carries its reply deadline in `endTime`, which the CASE_MANAGER sets the way it sets an embargo Invite's deadline: the Invite's `published` time plus the configured RSVP window, capped at the end of the active embargo ([CM-11-014](../specs/protocol.md#cm-11-014), [CM-28-012](../specs/protocol.md#cm-28-012)).
  When the deadline passes, the Invite closes and the invitee's record does not change.
  A reply after the deadline is still processed: an `Accept` joins the invitee and a `Reject` closes the record.
  The CASE_MANAGER can re-invite an actor with a fresh stub Invite on the same record and a new deadline, and the fresh Invite's `inReplyTo` names the earlier one ([CM-11-015](../specs/protocol.md#cm-11-015)).
  A re-invite of a participant that has closed is refused.
  When the active embargo is activated, revised or terminated while a stub Invite is outstanding, the CASE_MANAGER sends a replacement with the current terms and a new deadline.
  The replacement names the Invite it supersedes in the standard AS2 `inReplyTo` property.
  An `Accept` of the superseded Invite is refused, naming the replacement, and a `Reject` of it is honored ([CM-11-016](../specs/protocol.md#cm-11-016)).
- **Ask kind:** the Invite closes on `Accept` or `Reject` of it (`INVITE_ACTOR_TO_CASE_REPLY_TYPES`), and its expiry is stale: a late reply is still processed ([ASK-03-008](../specs/protocol.md#ask-03-008)).
- **Example artifact:** [invite_to_case.json](../examples/invite_to_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import rm_invite_to_case, json2md

print(json2md(rm_invite_to_case()))
```

---

## Accept Invite to Case

- **Protocol role:** The invited actor accepts and joins the case at RM Received.
  The CASE_MANAGER records the acceptance in the ledger, seats the participant, and then sends `Announce(VulnerabilityCase)` to seed the new participant's replica ([CM-17-004](../specs/protocol.md#cm-17-004)).
  Every other replica seats the new member from that ledger entry; the CASE_MANAGER sends no `Add(CaseParticipant)` for it ([CM-31-012](../specs/protocol.md#cm-31-012)).
- **Wire activity:** `Accept(Invite(Actor, target=VulnerabilityCaseStub))`.
  It joins the case and consents to the active embargo; it does not judge the case.
  The participant judges the case by answering the full-case Invite that follows.
- **Example artifact:** [accept_invite_to_case.json](../examples/accept_invite_to_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import accept_invite_to_case, json2md

print(json2md(accept_invite_to_case()))
```

---

## Reject Invite to Case

- **Protocol role:** The invited actor declines.
- **Triggering transition:** none — roster action.
- **Wire activity:** `Reject(Invite(Actor, target=VulnerabilityCaseStub))`.
- **Example artifact:** [reject_invite_to_case.json](../examples/reject_invite_to_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import reject_invite_to_case, json2md

print(json2md(reject_invite_to_case()))
```

---

## Invite Actor to Full Case

- **Protocol role:** After a participant joins, the CASE_MANAGER sends `Announce(VulnerabilityCase)`, starts the ledger replay, and then asks the participant to judge the case with the full-case Invite ([CM-11-010](../specs/protocol.md#cm-11-010), [ADR-0121](../../adr/0121-joined-participant-judges-the-case-by-full-case-invite.md)).
  The participant already holds the case, so the Invite names it by URI and asks one question: is this case valid?
- **Triggering transition:** none — the Invite asks; the reply moves RM.
- **Wire activity:** `Invite(Actor, target=VulnerabilityCase)`.
  The `object` is the participant, and the `target` is the plain case URI ([AKM-02-003](../specs/protocol.md#akm-02-003)).
  The CASE_MANAGER's ledger position when it issued the Invite travels in the standard AS2 `content` field, as the JSON dump of the `LedgerPosition` model, for example `{"logIndex":3,"entryHash":"<hash>"}`.
  It is a floor: the participant's reply must reach at least this point in the ledger ([VAM-04-011](../specs/protocol.md#vam-04-011)).
  An empty ledger is `logIndex` -1 with the case's `genesisHash` as `entryHash` ([CLP-08-004](../specs/protocol.md#clp-08-004)).
- **Ask kind:** the Invite closes on `Accept`, `TentativeReject` or `Reject` of it (`INVITE_ACTOR_TO_FULL_CASE_REPLY_TYPES`).

---

## Accept Full-Case Invite

- **Protocol role:** The participant judges the case valid (RV).
  The CASE_MANAGER records RM Received → Valid ([CM-11-011](../specs/protocol.md#cm-11-011)).
- **Wire activity:** `Accept(Invite(Actor, target=VulnerabilityCase))`.
  The reply carries the participant's own ledger position in `content`, in the same form as the Invite ([VAM-04-012](../specs/protocol.md#vam-04-012)).
  The CASE_MANAGER refuses a reply whose position is behind the Invite's, or names an entry its ledger does not hold, and writes nothing ([CM-11-012](../specs/protocol.md#cm-11-012)).

---

## Tentatively Reject Full-Case Invite

- **Protocol role:** The participant judges the case invalid (RI).
  The CASE_MANAGER records RM Received → Invalid.
  The stub Invite has no `TentativeReject`, because accepting a stub judges nothing ([CM-11-007](../specs/protocol.md#cm-11-007)).
- **Wire activity:** `TentativeReject(Invite(Actor, target=VulnerabilityCase))`, carrying the participant's ledger position in `content` ([VAM-04-013](../specs/protocol.md#vam-04-013)).

---

## Reject Full-Case Invite

- **Protocol role:** The participant closes the case (RC).
  The CASE_MANAGER records RM Received → Closed, and the participant stops receiving case content.
- **Wire activity:** `Reject(Invite(Actor, target=VulnerabilityCase))`, carrying the participant's ledger position in `content` ([VAM-04-014](../specs/protocol.md#vam-04-014)).

---

## Announce Vulnerability Case

- **Protocol role:** Sent by the CASE_MANAGER to a newly admitted participant after their `Accept(Invite)` clears embargo consent checks.
  The full `VulnerabilityCase` object is delivered inline so the recipient can seed its local replica ([PCR-02-002](../specs/protocol.md#pcr-02-002)).
  The same activity delivers a full case snapshot at every later lifecycle stage ([PCR-02-001](../specs/protocol.md#pcr-02-001)).
- **Triggering transition:** none — roster action following invite acceptance.
- **Wire activity:** `Announce(VulnerabilityCase)`.
- **Example artifact:** [announce_case.json](../examples/announce_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import announce_case, json2md

print(json2md(announce_case()))
```

---

## Create Case Participant

- **Protocol role:** Mints a new `CaseParticipant` record pairing an actor
  with a case and a set of CVD roles.
- **Triggering transition:** none — object construction.
- **Wire activity:** `Create(CaseParticipant)`.
- **Example artifact:** [create_participant.json](../examples/create_participant.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_participant, json2md

print(json2md(create_participant()))
```

---

## Add Case Participant to Case

- **Protocol role:** The Case Owner's request to the CASE_MANAGER to reinstate a removed participant.
  Reinstatement clears the participant's removal fact, so it is entitled to case content again; it does not ask the participant to accept again.
  `Add(CaseParticipant)` does not seat a new member: an actor joins a case by accepting its stub Invite (see [Accept Invite to Case](#accept-invite-to-case)).
- **Triggering transition:** none — the participant's record loses its removal fact.
- **Wire activity:** `Add(CaseParticipant)` with `target` = case URI.
- **Who may send:**
  The CASE_MANAGER accepts it only from the Case Owner.
  It refuses an `Add` that names a participant that is not removed, a participant that never joined the case, or no participant of the case.
  It also refuses an `Add` whose participant gives an `attributedTo` other than the actor of the record it names, because each replica finds its own copy of the record by that actor.
  A participant replica accepts it only from the CASE_MANAGER, as the direct notice below, and writes nothing from it.
- **Ledger:** the Case Owner's received `Add` is the one ledger entry for the reinstatement.
  Every replica applies the reinstatement from that entry, the reinstated participant's own included.
- **Catch-up:** once the participant is active again, the CASE_MANAGER sends it every ledger entry committed after its removal entry, in log order, so its copy of the ledger has no gap.
  A participant that is not a signatory to the active embargo stays inert: the CASE_MANAGER sends it that embargo's Invite instead, and the catch-up waits until it accepts.
- **Notice:** the CASE_MANAGER also sends the reinstated participant a direct `Add(CaseParticipant)` naming it, with `actor` set to the CASE_MANAGER and `attributedTo` set to the Case Owner.
  The notice is not ledgered.
- **Spec:** [Participant Removal](../vultron-spec/interactions.md#114-participant-removal-n).

The wire shape is the same whatever roles the participant holds; only `caseRoles` on the attached object differs.
A Vendor that holds the Case Owner role, reinstating a Coordinator:

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_coordinator_participant_to_case, json2md

print(json2md(add_coordinator_participant_to_case()))
```

---

## Remove Case Participant from Case

- **Protocol role:** The Case Owner's request to the CASE_MANAGER to remove a participant from active participation.
  Removal withdraws the participant's entitlement to case content; the participant's record stays on the case roster.
- **Triggering transition:** none — the participant's record gains a removal fact.
- **Wire activity:** `Remove(CaseParticipant)` with `target` = case URI.
  The case MUST be named in `target`; a `Remove` that names the case only in `origin` is not recognized as this message.
- **Who may send:**
  The CASE_MANAGER accepts it only from the Case Owner.
  It refuses a removal of the CASE_MANAGER's or the Case Owner's participant, and a removal that names no participant of the case.
  It also refuses a removal whose participant gives an `attributedTo` other than the actor of the record it names, because each replica finds its own copy of the record by that actor.
  A participant replica accepts it only from the CASE_MANAGER, as the direct notice below, and writes nothing from it.
- **Ledger:** the Case Owner's received `Remove` is the one ledger entry for the removal.
  Every replica applies the removal from that entry, the removed participant's own included.
- **Notice:** the CASE_MANAGER then sends the removed participant a direct `Remove(CaseParticipant)` naming it, with `actor` set to the CASE_MANAGER and `attributedTo` set to the Case Owner.
  The notice is not ledgered.
- **Spec:** [Participant Removal](../vultron-spec/interactions.md#114-participant-removal-n).
- **Example artifact:** [remove_participant_from_case.json](../examples/remove_participant_from_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import remove_participant_from_case, json2md

print(json2md(remove_participant_from_case()))
```
