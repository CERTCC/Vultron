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

## Message mapping

```python exec="true" idprefix=""
from vultron.metadata.msm.render import render_page

print(render_page("case_management", heading=False))
```

---

## Create Case

- **Protocol role:** The case owner mints a new `VulnerabilityCase` and adds
  the initial participant and report reference.
- **Triggering transition:** none — object construction precedes protocol state.
- **Wire activity:** `Create(VulnerabilityCase)`.
- **Example artifact:** [create_case.json](../examples/create_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_case, json2md

print(json2md(create_case()))
```

---

## Update Case

- **Protocol role:** The case owner broadcasts a changed `VulnerabilityCase`
  object — for example after a title edit or an ownership transfer is applied.
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

- **Protocol role:** An authorized participant offers a specific `CVDRole` on the
  case to another actor. The object type alone identifies the activity as a role
  offer rather than an ownership-transfer offer (ADR-0039).
- **Triggering transition:** none — roster action, not a state-machine event.
- **Wire activity:** `Offer(CaseParticipantRole)`, with `target` = the Actor
  receiving the role and `context` = the case.
- **Pattern:** `OfferCaseParticipantRolePattern` in
  `vultron/wire/as2/extractor/_instances.py`.
- **Factory:** `offer_case_participant_role_activity` in
  `vultron/wire/as2/factories/case.py`, re-exported from
  `vultron/wire/as2/factories/__init__.py`.
- **How-to:** [How to Delegate a Role to Another Participant](../../howto/activitypub/activities/role_delegation.md).
- **Example artifact:** [offer_case_participant_role.json](../examples/offer_case_participant_role.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import offer_case_participant_role, json2md

print(json2md(offer_case_participant_role()))
```

The `as_CaseParticipantRole` object carries the role. This offer is distinct from
`Offer(CaseParticipant)`, which forwards an actor recommendation to the Case Owner
and is covered on [General (GI) Messages](general.md).

---

## Accept Case Participant Role

- **Protocol role:** The target actor accepts the offered role and holds it from
  that point.
- **Triggering transition:** none — roster action.
- **Wire activity:** `Accept(Offer(CaseParticipantRole))`.
- **Pattern:** `AcceptCaseParticipantRolePattern` in
  `vultron/wire/as2/extractor/_instances.py`.
- **Factory:** `accept_case_participant_role_activity`.
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
- **Pattern:** `RejectCaseParticipantRolePattern` in
  `vultron/wire/as2/extractor/_instances.py`.
- **Factory:** `reject_case_participant_role_activity`.
- **How-to:** [How to Delegate a Role to Another Participant](../../howto/activitypub/activities/role_delegation.md).
- **Example artifact:** [reject_case_participant_role.json](../examples/reject_case_participant_role.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import reject_case_participant_role, json2md

print(json2md(reject_case_participant_role()))
```

The dedicated object type is required rather than a `target`-field discriminator
(SE-08-003), and the earlier `OFFER_CASE_MANAGER_ROLE` wire format
`Offer(VulnerabilityCase, target=CaseParticipant)` has been removed (SE-08-005).

---

## Offer Case Ownership Transfer

- **Protocol role:** The current case owner offers to transfer ownership to
  another actor (e.g. from a finder to a coordinator).
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

- **Protocol role:** A participant invites a new actor to join the case.
- **Triggering transition:** none — roster action.
- **Wire activity:** `Offer(Invite)` targeting the actor being invited.
- **Example artifact:** [invite_to_case.json](../examples/invite_to_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import rm_invite_to_case, json2md

print(json2md(rm_invite_to_case()))
```

---

## Accept Invite to Case

- **Protocol role:** The invited actor accepts and joins the case.
- **Triggering transition:** none — roster action; the case owner then sends
  `Announce(VulnerabilityCase)` to seed the new participant's DataLayer.
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

- **Protocol role:** Sent by the case owner to a newly admitted participant
  after their `Accept(Invite)` clears embargo consent checks. The full
  `VulnerabilityCase` object is delivered inline so the recipient can seed
  their local DataLayer (SYNC-09-001).
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
  `RemoveCaseParticipantFromCasePattern` discriminates on `target`, and
  `ActivityPattern` carries no `origin` field, so a `Remove` that names the case
  in `origin` alone matches no pattern and is never dispatched (#3438).
- **Example artifact:** [remove_participant_from_case.json](../examples/remove_participant_from_case.json).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import remove_participant_from_case, json2md

print(json2md(remove_participant_from_case()))
```
