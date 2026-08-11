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
  → SvcOfferCaseOwnershipTransferUseCase._prepare() sets:
      self._actor_id      = case_actor_id      ← CaseActor sends (CM-24-001)
      self._attributed_to = offering_actor_id  ← attribution (CM-24-002)
  → EmitOfferCaseOwnershipTransferNode
      constructs: Offer(VulnerabilityCase, target=transferee_id)
      actor:      case_actor_id                ← delegated-message contract
      attributed_to: offering_actor_id
      addressed:  to=[case_actor_id]           ← MUST (CM-21-005)
      queued in:  CaseActor's outbox           ← CM-24-004

CaseActor inbox receives Offer
  → OfferCaseOwnershipTransferReceivedUseCase:
      1. Records the Offer object (idempotent).
      2. Commits CaseLedgerEntry (offer-recorded).
      3. Announce(CaseLedgerEntry) → all participants.   ← CM-21-005 rationale
      4. Forwards Offer to transferee's inbox.
```

> **Correction (CONCERN-2170)**: Earlier descriptions of this flow stated the
> Offer was "queued in: offering actor's outbox" with `actor=offering_actor`
> and no `attributed_to`.  That was wrong.  Bug ISSUE-2142 confirmed the Coordinator rejects Offers
> whose `actor` names the Finder rather than the CaseActor.  The delegated
> pattern (CM-24-001 through CM-24-004) is the correct model.

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

### SvcOfferCaseOwnershipTransferUseCase._prepare()

- MUST call `_find_case_actor_id()` and set `self._actor_id = case_actor_id`
  (CM-24-001).
- MUST set `self._attributed_to = offering_actor_id` (CM-24-002).
- When no CaseActor exists: `self._actor_id = offering_actor_id`,
  `self._attributed_to = None` (CM-24-003).
- Pass `attributed_to` through to the BT builder (CM-24-004).

### EmitOfferCaseOwnershipTransferNode

- `_emit()` MUST use `actor=self.actor_id` (the CaseActor's ID) and pass
  `attributed_to=self.attributed_to` to the factory call.
- `to` MUST be `[case_actor_id]` — the Offer routes through the CaseActor
  (CM-21-005); the CaseActor processes it and forwards to the transferee.
- The `target` field of the Offer carries `transferee_id` (as before).

### EmitAcceptCaseOwnershipTransferNode

- `_emit()` MUST resolve `case_actor_id` from the DataLayer (using
  `_resolve_case_manager_id()` or equivalent) and set `to=[case_actor_id]`.
- Do not address the Accept to the offerer's actor ID.

### OfferCaseOwnershipTransferReceivedUseCase

Extend to:

1. Store the Offer object (existing behaviour — keep it).
2. Commit a `CaseLedgerEntry` recording the offer.
3. Forward the Offer to the transferee's inbox (new behaviour).

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
