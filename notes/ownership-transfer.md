---
title: Ownership Transfer Protocol — Routing and Cascade Model
status: active
kind: guidance
description: >
  Rules for the ownership-transfer routing model (ADR-0053, partially superseded
  by ADR-0148, proposed): the owner proposes Offer(Offer(Case)) to the
  CASE_MANAGER, which makes the one Offer the transferee answers, and every step
  routes through the CASE_MANAGER so every participant receives the
  CaseLedgerEntry broadcast; what each component must preserve, including that
  the transferee answers only the Offer it received; and the demo preconditions.
related_specs:
  - specs/case-management.yaml
  - specs/case-ledger-processing.yaml
  - specs/event-driven-control-flow.yaml
  - specs/behavior-tree-integration.yaml
  - specs/triggerable-behaviors.yaml
  - specs/handler-protocol.yaml
  - specs/participant-case-replica.yaml
  - specs/datalayer.yaml
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
  - vultron/demo/scenario/rvcv_handoff_demo.py
  - vultron/demo/scenario/rccv_handoff_demo.py
---

# Ownership Transfer Protocol — Routing and Cascade Model

Requirements: CM-21, CM-24, TRIG-11. Decision: ADR-0053, partially superseded by
ADR-0148 (proposed). The participant-facing
description is `docs/topics/case_lifecycle/ownership_transfer.md`. The close paths
without an answer (withdrawal and the binding deadline, both built) are in
[ownership-transfer-close-paths](ownership-transfer-close-paths.md). A
participant's `Reject` is a case event, ledgered like its `Accept` (CLP-02-012;
[case-ledger-authority](case-ledger-authority.md#two-meanings-of-reject)).

---

## Correct Routing Model (ADR-0053, ADR-0148)

Every step flows through the CASE_MANAGER, so every participant receives the
`Announce(CaseLedgerEntry)` for it. The owner proposes; the CASE_MANAGER makes the
one Offer of the transfer (ADR-0148).

### Proposal and Offer flow

```text
Case Owner calls trigger: offer-case-ownership-transfer
  → SvcOfferCaseOwnershipTransferUseCase._prepare() sets:
      self._actor_id = owner_id               ← the owner sends its own proposal
  → EmitProposeCaseOwnershipTransferNode
      constructs: Offer(Offer(VulnerabilityCase, target=Actor(transferee),
                              end_time?), context=case_id)
      addressed:  to=[case_actor_id]         ← MUST (CM-21-005)
      queued in:  the owner's own outbox     ← CM-24-004, ADR-0109

CASE_MANAGER inbox receives the proposal
  → ProposeCaseOwnershipTransferReceivedUseCase:
      sender guard: the Case Owner           ← CM-21-019
      clock decision: expire an overdue Offer ← CM-21-017
      guards: no open Offer; inner Offer names this case and a transferee
              that is neither the CASE_MANAGER nor the proposer
      1. Commits CaseLedgerEntry (propose_case_ownership_transfer).
      2. MakeOwnershipTransferOfferNode (CASE_MANAGER gate):
         Offer(VulnerabilityCase) id=ownership_offer_id(cm, case, proposal, owner),
         actor=case_actor_id, attributed_to=owner, to=[transferee];
         build → outbox → commit offer_case_ownership_transfer, one transaction.
      3. Announce(CaseLedgerEntry) → all participants, for each entry.
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

The declared rule is two-sided: `NAMED_ACTOR` at the CASE_MANAGER, `CASE_MANAGER`
at a participant (ADR-0129). The factory composes the guard from it; the
open-Offer guard runs right after it, so a sender with no standing is refused
before the Offer's state is read (#4437).

- **At the CASE_MANAGER** the addressee check `SenderIsOwnershipTransfereeNode`
  resolves the Accept's object through `recorded_ownership_offer()`
  (`vultron/core/participants/ownership_offer.py`) to a ledgered
  `offer_case_ownership_transfer` entry whose `target` is the sender. Then
  `OwnershipOfferOpenNode` requires no other answer recorded after it
  (`find_protocol_pair()`, which counts only replies after the latest matching
  request) and its deadline not passed. A second, different Accept is refused.
- **A redelivery changes nothing.** Re-running an old Accept could hand back
  ownership that a later Offer moved on, with no ledger entry; the open-Offer
  guard sets `is_redelivery` and the run reports `SKIPPED` (HP-01-003).
- **At any other replica** the sender must be the CASE_MANAGER, and a case the
  replica does not hold refuses (`SenderCheckContext.case_manager_required`,
  PCR-03-001).
- **An answer names the CASE_MANAGER's Offer by its id.** The ledgered Offer is the
  one the transferee holds, so `recorded_ownership_offer()` reads the entry by its
  `log_object_id` and follows no link (ADR-0148). Never match by time: with
  second-precision stamps a late answer closes a newer Offer recorded in the same
  second (#4565).
- **Either answer closes the Offer for the other.** The Accept and the Reject share
  `OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES`, so an Accept after a Reject (or the
  reverse) is refused as "already answered".
- **Only the Case Owner's proposal is made into an Offer** (CM-21-019): the
  sender guard runs before the expiry clock decision, the tree's first write
  (CLP-10-025), so a stranger's proposal leaves no entry, Offer or expiry. A
  redelivery is recognised by the Offer derived from the proposal, whose
  `attributedTo` must be the sender, not by the role: the sender may have handed
  ownership on since (`SenderIsOfferingCaseOwnerNode`, HP-01-003).
- **No sender is admitted for `Offer(VulnerabilityCase)` at the CASE_MANAGER**: it
  makes that Offer itself; a participant takes it from the CASE_MANAGER alone
  (CM-21-019, PCR-03-001).

### The Accepting Actor's Replica Updates via the CASE_MANAGER's Announce

Every replica, the accepting actor's included, updates through that `Announce`. If a
replica is not updating, the routing is wrong; never hand-deliver
([demo-scenario-authoring](demo-scenario-authoring.md)). The invariant: the accepting
actor's `case.attributed_to` changes on its own replica (`test/ci/invariants/`).

- **The `Accept` entry moves nothing on a replica.** Each change it causes follows as
  the CASE_MANAGER's own `Update` entry, old owner's record, new owner's record, then
  the case (`update_case_participant` ×2, `update_case_owner`), and a replica copies
  each one; it never derives the owner from the `Accept`'s sender (CLP-07-013,
  CM-23-016, #4439).

---

## What Each Component Must Preserve

### `SvcOfferCaseOwnershipTransferUseCase` and `EmitProposeCaseOwnershipTransferNode`

- `actor` is the proposing Case Owner, from its own store and outbox; no trigger
  executes a tree as the CASE_MANAGER (CM-24-004, ADR-0109). The bridge raises for
  an executing actor this container does not host (BT-05-005).
- A case always has a CASE_MANAGER (CM-24-006): when none resolves, fail; never send
  to the transferee directly.
- The proposal carries `context=case_id`, which the commit boundary requires
  (`payloadSnapshot.context` equals the case) and against which the inner Offer's
  object is checked. The trigger returns the proposal; the owner names it to
  withdraw (TRIG-11-006).
- **The transferee travels and is stored inline**, as an `Actor` object, never a
  bare id (DL-08-003): the ledger snapshot of the proposal and of the Offer carry it
  inline (CLP-07-006), so the CASE_MANAGER needs no actor-profile write. The factory
  wraps a bare id (#4843).

### `MakeOwnershipTransferOfferNode`

- Builds the Offer from the validated fields only; the inner Offer's id, `actor`
  and `to` are ignored (ADR-0148). Its id is `ownership_offer_id()`, derived from the
  proposal and its proposer, so a redelivery rebuilds the same Offer (OX-06-002) and
  another sender reusing the proposal id names another Offer.
- Build, queue and commit run in one `transaction()`: a failed commit takes the
  queued Offer back out, so no transferee holds an Offer the ledger does not
  record (CLP-07-015, SYNC-09-002).
- Faults are not caught; they escape to `BTBridge` as an internal error, never a
  refusal of the owner (ARCH-15-001). `NoOpenOwnershipOfferNode` treats a proposal
  as a redelivery only when its Offer is ledgered, so a redelivery after a fault
  makes it.

### `EmitAcceptCaseOwnershipTransferNode`

Resolve the CASE_MANAGER from the DataLayer and set `to=[case_actor_id]`; never
address the Accept to the offerer.

### `OfferCaseOwnershipTransferReceivedUseCase`

Runs at the transferee: intake keeps the CASE_MANAGER's Offer only as its
`ReceivedActivityRecord`, never under the id its sender chose (DL-06-006), and the
sender guard admits the CASE_MANAGER alone. Nothing is committed there.

- **Answer only the Offer intake archived.** The accept and reject triggers and the
  adapter read it with `read_received_activity`, so an actor that never received
  the Offer gets a not-found, whatever is stored under the Offer's id (DL-06-006).
  The `offer_case_ownership_transfer` entry has no replay effect: the transferee
  holds the Offer, the owner its proposal, and a bystander never answers
  (ADR-0148). Do not add a ledger-derived record of the Offer.

- **At the transferee, take the offerer from `attributed_to`, not `actor_id`**
  (#3012): the Offer is delegated, so its `actor` is the CASE_MANAGER. Honour
  `attributed_to` only when the sender is the case's CASE_MANAGER
  (`RecordedOwnershipOffer.offerer_id()`); nothing downstream re-checks it
  (CLP-07-003 checks `payloadSnapshot.actor`).
- **The snapshot builder's `_get_id` never falls back to `str(field)`**
  (`vultron/wire/as2/extractor/_builders.py`): `attributedTo` may be an inline object
  or array, and a Python repr in a hashed, replicated snapshot is unrecoverable
  (CLP-07-011).

### `create_accept_ownership_transfer_tree()`

Pass `case_id` to `create_receive_activity_tree`, the use case's `sender_rule` with
a `SenderCheckContext` naming the `OwnershipOfferRequest`, the open-Offer guard as
its precondition guard (`_reply_guards`), and put ONLY
`AcceptRecordedOwnershipOfferNode` in `manager_effects` (RSH-08-003: the change is
the CASE_MANAGER's to write). The
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
  `run_offer_reply_tree` in `core/use_cases/received/_offer_reply.py` runs either and
  reads its verdict.
- **The offerer learns of the decline from the broadcast.** It is not a recipient of
  the Reject (CM-21-010).
- **Replicas change no state.** `attributed_to` and every `CASE_OWNER` role stay; the
  entry only closes the Offer, which every reader learns from the ledger itself, so
  it has no replay effect (RSH-08-004).
- **"Open" is read from the ledger.** An Offer is open until the ledger holds an
  answer, withdrawal or expiry entry for it, found through `find_protocol_pair()`
  with `OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES` (CLP-11-001, CLP-11-003).
- **One open Offer per case (CM-21-014).** The CASE_MANAGER refuses a new proposal
  while an Offer is open; once closed, the owner may propose again to anyone, the
  decliner included. The check is `NoOpenOwnershipOfferNode`
  (`core/behaviors/case/nodes/ownership_offer_guard.py`, reading
  `open_ownership_offer()`) behind the CASE_MANAGER gate
  `case_manager_admits_ownership_proposal_guard`. A proposal whose derived Offer the
  ledger already records is a redelivery: the guard sets `is_redelivery` and
  `ownership_offer_verdict` reports `SKIPPED` (HP-01-003).
- **Withdrawal is an `Undo` of the proposal (CM-21-015).** The CASE_MANAGER derives
  the Offer id from the proposal id and its own id, so the owner needs nothing it
  learned from the ledger; the ledgered Undo is a reply that closes the Offer.

---

## Demos

- **Address the Accept to the CASE_MANAGER and hand-deliver nothing.** The handoff
  scenarios (`rvcv_handoff_demo.py`, `rccv_handoff_demo.py`) gate on the
  `accept_case_ownership_transfer` entry on a **non-party** actor's own replica (the
  Reporter), since only the CASE_MANAGER's fan-out can put it there (CM-21-007,
  EDF-06-002). `test/architecture/test_handoff_scenarios_verify_broadcast.py` enforces
  this for every scenario defining `_phase_ownership_handoff`.
- **Accept the CASE_MANAGER's Offer, not the proposal.** The CASE_MANAGER makes the
  Offer under an id it derives (CM-21-005, EDF-06-004); find it on the transferee
  with `find_ownership_transfer_offer_for_actor` and use that id in the accept
  trigger. Withdraw by the proposal id the offer trigger returned.
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
