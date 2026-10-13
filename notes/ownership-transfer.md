---
title: Ownership Transfer Protocol — Routing and Cascade Model
status: active
kind: guidance
description: >
  Rules for the ownership-transfer routing model (ADR-0053): the Offer and Accept
  route through the CASE_MANAGER so every participant receives the CaseLedgerEntry
  broadcast; what each component must preserve; replica-side materialization of
  the Offer from the ledger; and the demo preconditions.
related_specs:
  - specs/case-management.yaml
  - specs/case-ledger-processing.yaml
  - specs/event-driven-control-flow.yaml
  - specs/behavior-tree-integration.yaml
  - specs/triggerable-behaviors.yaml
  - specs/handler-protocol.yaml
  - specs/participant-case-replica.yaml
related_notes:
  - notes/case-communication-model.md
  - notes/protocol-event-cascades.md
  - notes/case-ledger-authority.md
  - notes/demo-scenario-authoring.md
  - notes/event-driven-control-flow.md
  - notes/ownership-transfer-close-paths.md
relevant_packages:
  - vultron/core/behaviors/case/nodes/
  - vultron/core/use_cases/received/actor/
  - vultron/demo/exchange/transfer_ownership_demo.py
  - vultron/demo/scenario/fvcv_handoff_demo.py
  - vultron/demo/scenario/fccv_handoff_demo.py
---

# Ownership Transfer Protocol — Routing and Cascade Model

Requirements: CM-21, CM-24, TRIG-11. Decision: ADR-0053. The participant-facing
description is `docs/topics/case_lifecycle/ownership_transfer.md`. The unbuilt close
paths (withdrawal, deadline) are planned in
[ownership-transfer-close-paths](ownership-transfer-close-paths.md). A
participant's `Reject` is a case event, ledgered like its `Accept` (CLP-02-012;
[case-ledger-authority](case-ledger-authority.md#two-meanings-of-reject)).

---

## Correct Routing Model (ADR-0053)

Both the Offer and the Accept MUST flow through the CASE_MANAGER, so every participant
receives the `Announce(CaseLedgerEntry)` for each step.

### Offer flow

```text
Offering actor calls trigger: offer-case-ownership-transfer
  → SvcOfferCaseOwnershipTransferUseCase._prepare() sets:
      self._actor_id      = case_actor_id      ← CASE_MANAGER sends (CM-24-001)
      self._requesting_actor_id = offering_actor_id  ← attribution (CM-24-002)
  → EmitOfferCaseOwnershipTransferNode
      constructs: Offer(VulnerabilityCase, target=transferee_id)
      actor:      case_actor_id                ← delegated-message contract
      attributed_to: offering_actor_id
      addressed:  to=[case_actor_id]           ← MUST (CM-21-005)
      queued in:  CASE_MANAGER outbox              ← CM-24-004

CASE_MANAGER inbox receives Offer
  → OfferCaseOwnershipTransferReceivedUseCase:
      1. Records the Offer object (idempotent).
      2. Commits CaseLedgerEntry (offer-recorded).
      3. Announce(CaseLedgerEntry) → all participants.
      4. Forwards Offer to transferee's inbox.
```

### Accept flow

```text
Accepting actor calls trigger: accept-case-ownership-transfer
  → EmitAcceptCaseOwnershipTransferNode
      constructs: Accept(Offer(VulnerabilityCase))
      addressed:  to=[case_actor_id]         ← MUST (CM-21-006)
      queued in:  accepting actor's outbox

CASE_MANAGER inbox receives Accept
  → AcceptCaseOwnershipTransferReceivedUseCase (guarded commit):
      sender: transferee of an open Offer it recorded      ← CM-21-011
              (anyone else: REFUSED, nothing written or sent)
      1. Commits CaseLedgerEntry (ownership-transferred).  ← CM-21-007
      2. Announce(CaseLedgerEntry) → all participants.
      3. AcceptRecordedOwnershipOfferNode applies role changes (CM-21-001–004)
         to the transferee the recorded Offer names, never the sender id.
```

### The Accept's sender check (CM-21-011)

`SenderIsOwnershipTransfereeNode` (`NAMED_ACTOR` kind, ADR-0129) is two-sided:

- **At the CASE_MANAGER** the Accept's object must resolve through
  `recorded_ownership_offer()` (`vultron/core/participants/ownership_offer.py`)
  to a ledgered `offer_case_ownership_transfer` entry whose `target` is the
  sender, with no other answer recorded after it (`find_protocol_pair()`, which
  counts only replies after the latest matching request). A second, different
  Accept is refused.
- **A redelivery changes nothing.** Re-running an old Accept could hand back
  ownership that a later Offer moved on, with no ledger entry; the guard sets
  `is_redelivery` and the run reports `SKIPPED` (HP-01-003).
- **At any other replica** the sender must be the CASE_MANAGER (PCR-03-001).
- **The transferee answers the forward, not the recorded Offer.** The forward
  (CM-21-005) has its own id and is not ledgered, so `recorded_ownership_offer()`
  also accepts an Offer the CASE_MANAGER issued itself for the same case and
  transferee, published no earlier than the recorded Offer (latest such entry).
- **Either answer closes the Offer for the other.** The Accept and the Reject share
  `OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES`, so an Accept after a Reject (or the
  reverse) is refused as "already answered".
- **The Offer itself is not sender-checked** (#4540): anyone can record an Offer
  naming itself and then accept it, so do not treat a recorded Offer as proof of
  the offerer's authority.

### The Accepting Actor's Replica Updates via the CASE_MANAGER's Announce

Every replica, the accepting actor's included, updates through that `Announce`. If a
replica is not updating, the routing is wrong; never hand-deliver
([demo-scenario-authoring](demo-scenario-authoring.md)). The invariant: the accepting
actor's `case.attributed_to` changes on its own replica (`test/ci/invariants/`).

---

## What Each Component Must Preserve

### `SvcOfferCaseOwnershipTransferUseCase` and `EmitOfferCaseOwnershipTransferNode`

- `actor` is the CASE_MANAGER and `attributed_to` the offering actor, both from the
  shared `delegated_authorship()` helper (CM-24-001, CM-24-002, CM-24-005), in
  `_prepare()` and again in the emit node's `_call_factory()` (CM-24-004).
- A case always has a CASE_MANAGER (CM-24-006): when none resolves, fail; never fall
  back to the offering actor (#3964 retires the remaining fallback arms).
- `to=[case_actor_id]`; the Offer's `target` carries `transferee_id`.

### `EmitAcceptCaseOwnershipTransferNode`

Resolve the CASE_MANAGER from the DataLayer and set `to=[case_actor_id]`; never
address the Accept to the offerer.

### `OfferCaseOwnershipTransferReceivedUseCase`

`create_offer_ownership_transfer_tree()` stores the Offer (idempotency guard), commits
through the guarded commit, and forwards via `ForwardOfferToTransfereeNode` passed as
`manager_effects`, so the factory wraps it in the CASE_MANAGER gate (BT-17-008). The
forwarded Offer has `actor=case_actor_id`, `attributed_to=` the original offerer,
`target` and `to=[transferee_id]` (CM-21-005).

- **Take the offerer from `attributed_to`, not `actor_id`** (#3012). The inbound Offer
  is delegated, so its `actor` is the CASE_MANAGER; reading `actor_id` attributes the
  offer to the CASE_MANAGER on every replica.
- **Honour `attributed_to` only in the delegated shape**, when the sender is this
  case's CASE_MANAGER (`_resolve_offering_actor_id()`). Otherwise any participant could
  forge the offerer of record: nothing downstream re-checks `attributed_to`
  (CLP-07-003 checks `payloadSnapshot.actor`). Pair any peer read of "who asked for
  this" with the same guard.
- **The snapshot builder's `_get_id` never falls back to `str(field)`**
  (`vultron/wire/as2/extractor/_builders.py`): `attributedTo` may be an inline object
  or array, and a Python repr in a hashed, replicated snapshot is unrecoverable
  (CLP-07-011).

### `create_accept_ownership_transfer_tree()`

Pass `case_id` to `create_receive_activity_tree`, `SenderIsOwnershipTransfereeNode`
as its `sender_guard`, and put ONLY `AcceptRecordedOwnershipOfferNode` in
`manager_effects` (RSH-08-003: the change is the CASE_MANAGER's to write). The
node reads the new owner from the recorded Offer, never from the sender id. The
factory already injects the guarded commit; a second `CommitCaseLedgerEntryNode`
is an unguarded second writer that forks the hash chain (CLP-09-001).

### The Reject Path (CM-21-010, CM-21-012 – CM-21-014)

A declined transfer has the same shape as an accepted one:

```text
Transferee calls trigger: reject-case-ownership-transfer      ← TRIG-11-005
  → Reject(Offer(VulnerabilityCase))
      addressed:  to=[case_actor_id]                          ← CM-21-010

CASE_MANAGER inbox receives Reject
  → RejectCaseOwnershipTransferReceivedUseCase:
      guard:  sender is the transferee of an open Offer
              it recorded                                     ← CM-21-013
              (anyone else: REFUSED, nothing written)
      1. Commits CaseLedgerEntry (reject_case_ownership_transfer).  ← CM-21-012
      2. Announce(CaseLedgerEntry) → all participants.
```

- **The Reject reuses the Accept's helper and guard** (CM-21-013):
  `create_reject_ownership_transfer_tree` is the Accept's tree with no effects, and
  `_run_ownership_answer` in `core/use_cases/received/actor/ownership.py` reads both
  verdicts.
- **The offerer learns of the decline from the broadcast.** It is not a recipient of
  the Reject (CM-21-010).
- **Replicas change no state.** `attributed_to` and every `CASE_OWNER` role stay; the
  entry only closes the Offer, which every reader learns from the ledger itself, so
  it has no replay effect (RSH-08-004).
- **"Open" is read from the ledger.** An Offer is open until the ledger holds an
  answer, withdrawal or expiry entry for it, found through `find_protocol_pair()`
  with `OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES` (CLP-11-001, CLP-11-003). The
  replica's `VultronOwnershipTransferOfferRecord` is bookkeeping (CLP-07-014), never
  the answer.
- **One open Offer per case (CM-21-014).** The CASE_MANAGER refuses a new Offer while
  one is open; once closed, the owner may offer again to anyone, the decliner
  included. The check is `NoOpenOwnershipOfferNode`
  (`core/behaviors/case/nodes/ownership_offer_guard.py`, reading
  `open_ownership_offer()`) behind the CASE_MANAGER gate
  `case_manager_admits_ownership_offer_guard`. The gate is load-bearing: the
  transferee runs the same Offer tree on the forward, and its replica already holds
  the ledgered Offer, still open. An Offer the ledger already records is a
  redelivery: the guard sets `is_redelivery` and `ownership_offer_verdict` reports
  `SKIPPED` (HP-01-003), so it is neither refused nor committed or forwarded again.

---

## Replica-side Materialization (SYNC Path)

On a replica that learns of an Offer only from the ledger, the Offer never arrives by
inbox, yet `SvcAcceptCaseOwnershipTransferUseCase._prepare` must `dl.read(offer_id)`.
The announce tree's `OfferOwnershipTransferEffects` slot
(`IsOfferOwnershipTransferEventNode`, `ApplyOfferOwnershipTransferFromLedgerNode`)
materializes a `VultronOwnershipTransferOfferRecord` from the entry's snapshot.

- **Store a full record or none.** `case_id` is a required `UriString`; a half-record
  satisfies the read and fails on the case lookup one line later.
- **Name the field `case_id`, not `object_`.** The DataLayer rehydrates AS2 reference
  fields (`object_`, `target`, `origin`, `result`, `instrument`) into typed objects on
  read. `_prepare` reads `case_id`, then falls back to `object_` for the wire Offer the
  inbox path stores.
- **Status (SYNC-12-001):** SUCCESS when there is nothing to apply; FAILURE only when a
  well-formed record could not be written, which blocks `PersistReceivedLogEntry`.

### Two consumers, one key

| Consumer | Needs |
|---|---|
| `SvcAcceptCaseOwnershipTransferUseCase._prepare` | anything from which a case id is recoverable |
| `TriggerActivityAdapter.accept_case_ownership_transfer` | an `_OfferCaseOwnershipTransferActivity` |

The adapter rebuilds the wire Offer from the core record (`_offer_from_core_record`)
with the same `offer_case_ownership_transfer_activity` factory the offerer uses, so
both paths produce an identical Accept. It lives in the adapter because core may not
import wire (ARCH-03-001). So the record also carries `actor_id` and `target_id`
(DL-06-002), and `object_` is the inline case read from the replica and projected with
`as_VulnerabilityCase.from_core`; a bare URI fails the factory with a 422.

---

## Demos

- **Address the Accept to the CASE_MANAGER and hand-deliver nothing.** The handoff
  scenarios (`fvcv_handoff_demo.py`, `fccv_handoff_demo.py`) gate on the
  `accept_case_ownership_transfer` entry on a **non-party** actor's own replica (the
  Finder), since only the CASE_MANAGER's fan-out can put it there (CM-21-007,
  EDF-06-002). `test/architecture/test_handoff_scenarios_verify_broadcast.py` enforces
  this for every scenario defining `_phase_ownership_handoff`.
- **Accept the forwarded Offer, not the original.** The CASE_MANAGER forwards a new
  Offer with a new id (CM-21-005); find it on the transferee with
  `find_ownership_transfer_offer_for_actor` and use that id in the accept trigger.
- **The exchange demo needs a CASE_MANAGER-owned case.** `setup_initialized_case`
  leaves no CASE_MANAGER participant; use
  `vultron.demo.helpers.workflow.setup_canonical_case`.
- **The transferee must be known to the CASE_MANAGER**: in its address book
  (`seed_peer(client, local_actor_id=case_actor_id, ...)`) and seated on its replica
  through the stub Invite (`seat_participant_through_stub_invite`). The snapshot's
  `target` must be inline (CLP-07), and `Add(CaseParticipant)` never seats a member
  (CM-31-011), so a missing transferee fails at commit with
  `payloadSnapshot.target must be an inline object`.
- **The exchange demo drives every step through its actor's trigger**
  (DEMOMA-05-001): the vendor's `offer-case-ownership-transfer`, then the
  coordinator's `accept-` or `reject-case-ownership-transfer`. It gates on the
  CASE_MANAGER's ledger entries (`offer_case_ownership_transfer`,
  `reject_case_ownership_transfer`), not a timed read (EDF-06): the reject path's
  "owner unchanged" check means nothing until the Reject is known processed.
