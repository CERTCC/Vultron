---
title: Ownership Transfer Protocol — Routing and Cascade Model
status: active
description: >
  Implementation guidance for the ownership-transfer routing model introduced
  in ADR-0053: Offer and Accept MUST route through the CaseActor so that
  all participants receive CaseLedgerEntry broadcast notifications for both
  the pending offer and the completed transfer.
related_specs:
  - specs/case-management.yaml
related_notes:
  - notes/case-communication-model.md
  - notes/protocol-event-cascades.md
relevant_packages:
  - vultron/core/behaviors/case/nodes/
  - vultron/core/use_cases/received/actor/
  - vultron/demo/scenario/fvcv_handoff_demo.py
---

# Ownership Transfer Protocol — Routing and Cascade Model

**Source**: ADR-0053 / CONCERN-1755 planning session 2026-08-05.
Normative requirements: CM-21-005, CM-21-006, CM-21-007.

---

## The Problem (Pre-ADR-0053)

Before ADR-0053 the ownership-transfer protocol had two routing gaps:

1. **Offer sent directly to transferee** — `EmitOfferCaseOwnershipTransferNode`
   addressed the Offer to the transferee's inbox, bypassing the CaseActor.
   No CaseLedgerEntry was written for the offer-in-flight; participants not
   involved in the negotiation received no notification.

2. **Accept sent directly to offerer** — `EmitAcceptCaseOwnershipTransferNode`
   addressed the Accept to the offerer's inbox, bypassing the CaseActor.
   `AcceptCaseOwnershipTransferReceivedUseCase` only ran when the Accept was
   manually self-delivered (the `post_to_inbox_and_wait` workaround in
   `fvcv_handoff_demo.py`).  No CaseLedgerEntry was written after the role
   change; the Announce broadcast never fired.

---

## Correct Routing Model (ADR-0053)

Both activities MUST flow through the CaseActor.

### Offer flow

```text
Offering actor calls trigger: offer-case-ownership-transfer
  → EmitOfferCaseOwnershipTransferNode
      constructs: Offer(VulnerabilityCase, target=transferee_id)
      addressed:  to=[case_actor_id]         ← MUST (CM-21-005)
      queued in:  offering actor's outbox

CaseActor inbox receives Offer
  → OfferCaseOwnershipTransferReceivedUseCase:
      1. Records the Offer object (idempotent).
      2. Commits CaseLedgerEntry (offer-recorded).
      3. Announce(CaseLedgerEntry) → all participants.   ← CM-21-005 rationale
      4. Forwards Offer to transferee's inbox.
```

### Accept flow

```text
Accepting actor calls trigger: accept-case-ownership-transfer
  → EmitAcceptCaseOwnershipTransferNode
      constructs: Accept(Offer(VulnerabilityCase))
      addressed:  to=[case_actor_id]         ← MUST (CM-21-006)
      queued in:  accepting actor's outbox

CaseActor inbox receives Accept
  → AcceptCaseOwnershipTransferReceivedUseCase (guarded-commit pattern):
      guard:  receiving_actor_id == case_actor_id (skip if not CaseActor)
      1. AcceptCaseOwnershipTransferNode applies role changes (CM-21-001–004).
      2. Commits CaseLedgerEntry (ownership-transferred).  ← CM-21-007
      3. Announce(CaseLedgerEntry) → all participants.
```

---

## Implementation Checklist

### EmitOfferCaseOwnershipTransferNode

- `_emit()` MUST resolve `case_actor_id` from the DataLayer and set
  `to=[case_actor_id]`.  Do not use the `transferee_id` as the `to` field.
- The `target` field of the Offer carries `transferee_id` (as before).

### EmitAcceptCaseOwnershipTransferNode

- `_emit()` MUST resolve `case_actor_id` from the DataLayer (using
  `_resolve_case_manager_id()` or equivalent) and set `to=[case_actor_id]`.
- Do not address the Accept to the offerer's actor ID.

### OfferCaseOwnershipTransferReceivedUseCase

Extend to:

1. Store the Offer object (existing behaviour — keep it).
2. Commit a `CaseLedgerEntry` recording the offer.
3. Forward the Offer to the transferee's inbox.

**Forwarded-Offer wire format** (CM-21-005, mirrors Invite-flow analogy):

```
Offer(VulnerabilityCase,
    actor        = case_actor_id,       ← CaseActor is the sender
    attributed_to = original_actor_id,  ← Vendor1's intent carried forward
    target       = transferee_id,
    to           = [transferee_id],     ← MUST be set (delivery requirement)
)
```

`attributed_to` must be threaded through `TriggerActivityPort.offer_case_ownership_transfer`
so the factory can stamp it on the wire object.

Use the guarded-commit pattern: only runs when `receiving_actor_id == case_actor_id`.

### AcceptCaseOwnershipTransferReceivedUseCase / ownership_transfer_tree.py

Extend `create_accept_ownership_transfer_tree()` to append a
`CommitCaseLedgerEntryNode` (and fan-out) after `AcceptCaseOwnershipTransferNode`.

Use the guarded-commit pattern: the `BTBridge` call already runs in the
CaseActor's context; add a `CheckIsCaseManagerNode` guard as the first
child of the root Sequence so that the tree is a no-op on non-CaseActor
replicas that happen to receive the same Accept activity.

### fvcv_handoff_demo.py

Remove the `post_to_inbox_and_wait` self-delivery block (lines ~427–434).
The Accept now reaches the CaseActor automatically because
`EmitAcceptCaseOwnershipTransferNode` addresses it there.

After the Vendor1 offer-trigger returns, poll Coordinator's DataLayer with
`find_ownership_transfer_offer_for_actor(coordinator_client, case_id, transferee_id=coordinator.id_)`
to discover the forwarded Offer ID. Use the returned ID — **NOT** `ownership_offer.id_` — for
the `accept-case-ownership-transfer` trigger body.

> **Rationale:** `OfferCaseOwnershipTransferReceivedUseCase` creates a new Offer with a new ID
> (CM-21-005). The original Offer exists only in the CaseActor's DataLayer; polling for it on
> Coordinator's container (`wait_for_object_stored(original_offer.id_)`) will never match.
> The discriminator-based poll (`find_ownership_transfer_offer_for_actor`) scans for semantic
> properties (type + target + object) rather than identity (specific ID).

---

## Analogy: Invite/Accept Handshake

This routing model is identical to the Invite/Accept handshake (ADR-0026,
PCR-08-007/008):

| Invite/Accept | Ownership Transfer |
|---|---|
| `Invite` sent **by** CaseActor | `Offer` addressed **to** CaseActor → forwarded |
| `Accept(Invite)` addressed **to** CaseActor | `Accept(Offer)` addressed **to** CaseActor |
| CaseActor creates `CaseParticipant` | CaseActor applies CM-21 role changes |
| CaseLedgerEntry → broadcast | CaseLedgerEntry → broadcast |

Use this analogy when explaining the model to new contributors.

---

## Replica-side Materialization (SYNC Path)

When a participant joins a case that already has an ownership-transfer offer
in flight, or when a Coordinator replica receives the ledger broadcast for
`offer_case_ownership_transfer`, the Offer object must be materialized from
the `Announce(CaseLedgerEntry)` entry — it does **not** arrive via the HTTP
inbox path.

The announce tree (`create_announce_log_entry_tree`) has a Selector slot for
`OfferOwnershipTransferEffects`. The two BT nodes that wire this slot are:

- `IsOfferOwnershipTransferEventNode` — Condition: checks
  `entry.event_type == "offer_case_ownership_transfer"`
- `ApplyOfferOwnershipTransferFromLedgerNode` — Action: extracts `offer_id`
  from `payload_snapshot["id"]` and `case_id` from `payload_snapshot["object"]`,
  creates a `VultronOwnershipTransferOfferRecord`, and saves it to the
  DataLayer so that `SvcAcceptCaseOwnershipTransferUseCase._prepare` can
  `dl.read(offer_id)` without a 404.

**Why this is needed**: `SvcAcceptCaseOwnershipTransferUseCase._prepare` calls
`self._dl.read(request.offer_id)` to resolve the case ID embedded in the
offer. If the Coordinator replica never materialized the Offer object (because
it arrived only via the SYNC path, not the HTTP inbox), `_prepare` raises
`VultronNotFoundError("VultronOwnershipTransferOfferRecord", offer_id)`.

This is analogous to how report-offer backfill works in the invite flow — the
ledger entry carries the full payload snapshot, and the announce-tree effect
node reconstructs the core object from it.

**Spec ref**: CM-21-007.

---

## Guarded-Commit Pattern Reminder

`AcceptCaseOwnershipTransferReceivedUseCase` is a **received-side** use case.
Both the CaseActor and participant replicas may receive the same Accept
activity (once routing is corrected). The guarded-commit ensures only the
CaseActor writes the ledger entry:

```python
if request.receiving_actor_id != case_actor_id:
    return  # not CaseActor — skip commit
```

See `notes/case-communication-model.md` § "Antipattern: Received-Side
Guarded Commit with Foreign CaseActor ID" for the full pattern.
