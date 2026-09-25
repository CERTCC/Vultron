---
stakeholder_type: [platform-developer, project-contributor]
level: 300
introduces: [Case Ownership Transfer]
---

# Case Ownership Transfer

A case has at most one owner at a time: the participant holding the `CASE_OWNER` role, who makes decisions for the case ([CM-21-001](../../reference/specs/protocol.md#cm-21)).
Ownership can move from one participant to another — for example, when a vendor hands a case to a coordinator.
This page explains how that transfer works and why every step of it goes through the [CASE_MANAGER](case_manager_and_ledger.md).

---

## Why the transfer goes through the CASE_MANAGER

A change of owner matters to everyone in the case, not only to the two participants involved.
Every participant needs to know who decides for the case now.
The only way a participant learns about a change to the case is through an entry in the case ledger, and only the CASE_MANAGER writes those entries ([The CASE_MANAGER and the Case Ledger](case_manager_and_ledger.md)).

So both the offer and the answer are sent to the CASE_MANAGER, not to the other party directly ([CM-21-005, CM-21-006, CM-21-010](../../reference/specs/protocol.md#cm-21), [ADR-0053](../../adr/0053-ownership-transfer-routed-via-caseactor.md)).
If they went directly between the two parties, no ledger entry would be written, and the other participants would never learn that ownership had changed.

---

## The offer

```text
Offering actor sends trigger: offer-case-ownership-transfer
  → Case Actor sends Offer(VulnerabilityCase, target=transferee)
      actor:        case_actor_id       (delegated-message contract)
      attributed_to: offering_actor_id
      to:           [case_actor_id]     ← MUST route through Case Actor (CM-21-005)

Case Actor inbox receives Offer:
  1. Records the Offer.
  2. Commits CaseLedgerEntry (offer-recorded).
  3. Announce(CaseLedgerEntry) → all participants.   ← all parties learn the offer
  4. Forwards Offer to transferee's inbox.
```

The owner asks for the transfer, and the offer goes to the CASE_MANAGER — in the prototype, the Case Actor.
The CASE_MANAGER records the offer in the ledger, so every participant learns that a transfer is being offered, and then forwards the offer to the proposed new owner.

The CASE_MANAGER sends the offer under its own identity, with the owner who asked for it named as the author (`attributed_to`).
This is the delegated-message contract that every message the CASE_MANAGER sends on a participant's behalf follows ([CM-24-001 through CM-24-004](../../reference/specs/protocol.md#cm-24)).

## The answer

```text
Accepting actor sends trigger: accept-case-ownership-transfer
  → Accept(Offer(VulnerabilityCase))
      to: [case_actor_id]     ← MUST route through Case Actor (CM-21-006)

Case Actor inbox receives Accept:
  1. Applies the CASE_OWNER role change (CM-21-001 through CM-21-004).
  2. Commits CaseLedgerEntry (ownership-transferred).   ← CM-21-007
  3. Announce(CaseLedgerEntry) → all participants.
```

The proposed owner answers the CASE_MANAGER, not the participant who made the offer.
On an acceptance, the CASE_MANAGER moves the `CASE_OWNER` role in a single step: the previous owner loses it and the new owner gains it together, so the case never has two owners or none ([CM-21-001 through CM-21-004](../../reference/specs/protocol.md#cm-21)).
The previous owner keeps any other roles it held and stays a participant in the case ([CM-21-008, CM-21-009](../../reference/specs/protocol.md#cm-21)).
The CASE_MANAGER then records the completed transfer in the ledger and sends the entry to every participant ([CM-21-007](../../reference/specs/protocol.md#cm-21)).
The new owner's own copy of the case is updated by that same entry; nothing is delivered to it separately.

A refusal is also sent to the CASE_MANAGER ([CM-21-010](../../reference/specs/protocol.md#cm-21)), and ownership stays where it was.
What the CASE_MANAGER does after a refusal is not yet specified.
Today it only logs the refusal: no ledger entry records it, and the participant who made the offer is not told.
Whether a refusal should be recorded, how the offerer learns of it, and whether the case can be offered again are tracked in [#3748](https://github.com/CERTCC/Vultron/issues/3748).

---

## The same pattern as an invitation

Ownership transfer follows the same pattern as inviting an actor to join a case ([ADR-0026](../../adr/0026-caseactor-routed-actor-suggestion.md)):

| Invite/Accept | Ownership Transfer |
|---|---|
| `Invite` sent **by** the CASE_MANAGER | `Offer` addressed **to** the CASE_MANAGER, then forwarded |
| `Accept(Invite)` addressed **to** the CASE_MANAGER | `Accept(Offer)` addressed **to** the CASE_MANAGER |
| The CASE_MANAGER creates the `CaseParticipant` | The CASE_MANAGER moves the `CASE_OWNER` role |
| `CaseLedgerEntry` → every participant | `CaseLedgerEntry` → every participant |

In both, the CASE_MANAGER sits in the middle because it is the only participant that writes to the ledger, and its entries reach everyone.

---

## See also

- [Case Management Messages](../../reference/messages/case_management.md#offer-case-ownership-transfer) — the `Offer`, `Accept`, and `Reject` activities on the wire
- [Other Demos: transfer-ownership](../../tutorials/other_demos.md#transfer-ownership) — run a transfer end to end
- [The Case Model](case_model.md) — `VulnerabilityCase`, participants, and the `CASE_OWNER` role
- [The CASE_MANAGER and the Case Ledger](case_manager_and_ledger.md) — how a ledger entry reaches every participant
- [Case Ownership in a federation](../future_work/federation.md#case-ownership) — future work on ownership when each organization runs its own service
- [Open questions: cases and participants](../future_work/open_questions.md#cases-and-participants) — including where the CASE_MANAGER lives after ownership moves
- [ADR-0053](../../adr/0053-ownership-transfer-routed-via-caseactor.md) — decision record for CASE_MANAGER-routed ownership transfer
- [ADR-0026](../../adr/0026-caseactor-routed-actor-suggestion.md) — CaseActor-routed actor suggestion and invitation flow
