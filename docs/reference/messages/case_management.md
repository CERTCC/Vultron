---
stakeholder_type: [platform-developer, project-contributor]
level: 400
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
The **CASE_MANAGER** is the case's single-writer authority: it mints and updates the `VulnerabilityCase` object, records every case-scoped message in the ledger, and delivers case snapshots to participants (spec [§5.4.1](../vultron-spec/index.md#541-single-writer-authority), [ADR-0088](../../adr/0088-consolidate-case-authority-determination.md)).
The CASE_MANAGER acts on the Case Owner's behalf; the two roles are often held by the same actor but need not be.
The 300-level introduction is [The Case Manager and the Case Ledger](../../topics/case_lifecycle/case_manager_and_ledger.md).

## Message mapping

```python exec="true" idprefix=""
from vultron.metadata.msm.render import render_page

print(render_page("case_management", heading=False))
```

---

## Create Case

- **Protocol role:** The CASE_MANAGER mints a new `VulnerabilityCase`, seats the initial participants (the Case Owner and the reporter), and links the report, then sends the completed case once to the report submitter as the trust bootstrap (spec [§4.5](../vultron-spec/index.md#45-trust-and-bootstrap-semantics); [CBT-01-001](../specs/protocol.md#cbt-01-001), [CM-22-002](../specs/protocol.md#cm-22-002)).
- **Triggering transition:** none — object construction precedes protocol state.
- **Wire activity:** `Create(VulnerabilityCase)`.
- **Example artifact:** [create_case.json](../examples/create_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_case, json2md

print(json2md(create_case()))
```

---

## Update Case

- **Protocol role:** The CASE_MANAGER records a changed `VulnerabilityCase` object — for example after a title edit or an ownership transfer is applied — and fans it out through the ledger ([§5.4.2](../vultron-spec/index.md#542-routing-topology)).
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
  Roles are granted through the case's authority chain ([§11.1](../vultron-spec/index.md#111-role-assignment-n)).
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

The dedicated object type is preferred over a `target`-field discriminator ([SE-08-003](../specs/protocol.md#se-08-003)), and the earlier wire format `Offer(VulnerabilityCase, target=CaseParticipant)` for offering a role has been removed ([SE-08-005](../specs/protocol.md#se-08-005)).

---

## Offer Case Ownership Transfer

- **Protocol role:** The current Case Owner offers to transfer ownership to another actor (e.g. from a reporter to a coordinator).
  The offer is routed through the CASE_MANAGER, which records it in the ledger ([§11.3](../vultron-spec/index.md#113-case-ownership-transfer-n)); see [Case Ownership Transfer](../../topics/case_lifecycle/ownership_transfer.md).
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
  See [§11.2](../vultron-spec/index.md#112-invitation-and-acceptance-n).
- **Triggering transition:** none — roster action.
- **Wire activity:** `Offer(Invite)` targeting the actor being invited.
- **Example artifact:** [invite_to_case.json](../examples/invite_to_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import rm_invite_to_case, json2md

print(json2md(rm_invite_to_case()))
```

---

## Accept Invite to Case

- **Protocol role:** The invited actor accepts and joins the case at RM Received.
  The CASE_MANAGER records the acceptance in the ledger, seats the participant, and then sends `Announce(VulnerabilityCase)` to seed the new participant's replica ([CM-17-004](../specs/protocol.md#cm-17-004)).
- **Wire activity:** `Accept(Invite)`.
- **Example artifact:** [accept_invite_to_case.json](../examples/accept_invite_to_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import accept_invite_to_case, json2md

print(json2md(accept_invite_to_case()))
```

---

## Reject Invite to Case

- **Protocol role:** The invited actor declines.
- **Triggering transition:** none — roster action.
- **Wire activity:** `Reject(Invite)`.
- **Example artifact:** [reject_invite_to_case.json](../examples/reject_invite_to_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import reject_invite_to_case, json2md

print(json2md(reject_invite_to_case()))
```

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

- **Protocol role:** Attaches a `CaseParticipant` record to the case.
- **Triggering transition:** none — roster operation.
- **Wire activity:** `Add(CaseParticipant)` with `target` = case URI.
- **How-to:** [How to Seat a Participant on an Existing Case](../../howto/activitypub/activities/initialize_participant.md).
- **Example artifact:** [add_vendor_participant_to_case.json](../examples/add_vendor_participant_to_case.json).

The wire shape is the same whatever roles the participant holds; only
`caseRoles` on the attached object differs. A Vendor seating itself:

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_vendor_participant_to_case, json2md

print(json2md(add_vendor_participant_to_case()))
```

A Vendor seating a Coordinator:

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_coordinator_participant_to_case, json2md

print(json2md(add_coordinator_participant_to_case()))
```

A Vendor seating the Finder, who is also the Reporter here. A single
`CaseParticipant` carries as many roles as the actor holds on the case:

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_finder_participant_to_case, json2md

print(json2md(add_finder_participant_to_case()))
```

---

## Remove Case Participant from Case

- **Protocol role:** Removes a participant from the case roster.
- **Triggering transition:** none — roster operation.
- **Wire activity:** `Remove(CaseParticipant)` with `target` = case URI.
  The case MUST be named in `target`; a `Remove` that names the case only in `origin` is not recognized as this message.
- **Example artifact:** [remove_participant_from_case.json](../examples/remove_participant_from_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import remove_participant_from_case, json2md

print(json2md(remove_participant_from_case()))
```
