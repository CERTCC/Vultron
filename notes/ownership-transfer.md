---
title: Ownership Transfer Protocol — Routing and Cascade Model
status: active
kind: guidance
description: >
  Rules for the ownership-transfer routing model (ADR-0053, ADR-0148, ADR-0199):
  the owner sends its own Offer(VulnerabilityCase) to the CASE_MANAGER, which
  ledgers it and makes its own Offer, the one the transferee answers, and every
  step routes through the CASE_MANAGER so every participant receives the
  CaseLedgerEntry broadcast; what each component must preserve, including that
  the transferee answers only the Offer it received and must be an active
  participant; and the demo preconditions.
related_specs:
  - specs/actor-knowledge-model.yaml
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
relevant_packages:
  - vultron/core/behaviors/case/nodes/
  - vultron/core/use_cases/received/actor/
  - vultron/demo/exchange/transfer_ownership_demo.py
  - vultron/demo/scenario/rvcv_handoff_demo.py
  - vultron/demo/helpers/owner_decision_story/
---

# Ownership Transfer Protocol — Routing and Cascade Model

Requirements: CM-21, CM-24, TRIG-11. Decisions: ADR-0053, partially superseded by
ADR-0148, which narrows the transferee check to an active participant, entitled to
case content and holding the case, which the Offer names by typed reference
(ADR-0165); ADR-0199 makes the owner's proposal its own
`Offer(VulnerabilityCase)`. The participant-facing description is
`docs/topics/case_lifecycle/ownership_transfer.md`. An Offer can also close without
an answer, by the owner's withdrawal or its binding deadline
(CM-21-015 to CM-21-017). Every closing entry's `semantic_type` is in
`OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES`, which every "is it open?" reader uses,
so a new way to close an Offer needs no other change to close it. A
participant's `Reject` is a case event, ledgered like its `Accept` (CLP-02-016;
[case-ledger-authority](case-ledger-authority.md#two-meanings-of-reject)).

---

## Correct Routing Model (ADR-0053, ADR-0148)

Every step flows through the CASE_MANAGER, so every participant receives the
`Add(CaseLedgerEntry)` for it, the commit's `Add` to the case's ledger
(ADR-0204). The owner offers the case with its own Offer; the CASE_MANAGER makes
the Offer the transferee answers (ADR-0148, ADR-0199).

- **One shape, two senders.** The Owner's Offer and the CASE_MANAGER's are both
  `Offer(VulnerabilityCase)` with the transferee as `target`, one semantic type and
  one received tree; the receiver's path tells them apart (HP-01-038). Both are
  ledgered as `offer_case_ownership_transfer`, so every reader of "the Offer"
  (`ownership_offer.py`) keeps only the CASE_MANAGER's own: its `actor` is the
  CASE_MANAGER and its id is the one derived from its `inReplyTo` and
  `attributedTo` (CM-21-028). The `actor` alone is not enough, because an Owner
  that is also the CASE_MANAGER (CM-02-010) sends its own Offer as the
  CASE_MANAGER. An answer naming the Owner's Offer names nothing to accept.

### Proposal and Offer flow

```text
Case Owner calls trigger: offer-case-ownership-transfer
  → SvcOfferCaseOwnershipTransferUseCase._prepare() sets:
      self._actor_id = owner_id               ← the owner sends its own Offer
  → EmitProposeCaseOwnershipTransferNode
      constructs: Offer(VulnerabilityCase), target=Actor(transferee),
                  context=case_id, end_time?
      addressed:  to=[case_actor_id] only    ← MUST (CM-21-005); no CASE_MANAGER
                                               fails the emit, never the transferee
      queued in:  the owner's own outbox     ← CM-24-010, ADR-0109

CASE_MANAGER inbox receives the Owner's Offer (manager path)
  → OfferCaseOwnershipTransferReceivedUseCase:
      sender guard: the Case Owner           ← CM-21-019 (no notice, CLP-05-006)
      clock decision: expire an overdue Offer ← CM-21-017
      guards (refusal notice): no open Offer; a transferee that is neither the
              CASE_MANAGER nor the Owner, and is an active participant
              (CM-21-014, CM-21-021, CM-21-026)
      1. Commits CaseLedgerEntry (offer_case_ownership_transfer, the Owner's).
      2. MakeOwnershipTransferOfferNode (CASE_MANAGER gate):
         Offer(VulnerabilityCase) id=ownership_offer_id(cm, case, owner_offer, owner),
         actor=case_actor_id, attributed_to=owner, in_reply_to=owner_offer,
         to=[transferee];
         build → outbox → commit offer_case_ownership_transfer, one transaction.
      3. Add(CaseLedgerEntry) → all participants, for each entry.
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
      guards: the Offer is open; the transferee is still an active
              participant (OwnershipTransfereeActiveNode)  ← CM-21-022
      1. Commits CaseLedgerEntry (ownership-transferred).  ← CM-21-007
      2. Add(CaseLedgerEntry) → all participants.
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
  guard sets `is_redelivery` and the run reports `SKIPPED` (HP-01-014).
- **The transferee's standing is one predicate at all three checks.** The trigger,
  the proposal guard and the Accept guard all ask `may_act_on_case()`
  (`core/participants/recipients/`), so a participant whose closure is
  recorded is refused too: the Offer is case content (CM-23-004). The Accept's
  check is a precondition guard after the open-Offer guard, not part of the
  sender check:
  a redelivered Accept stays `SKIPPED` after the new owner lapses (HP-01-014).
  The Reject moves nothing, so it is not checked: CM-21-022 names the Accept.
- **A new owner with no participant record raises** in
  `_TransferCaseOwnershipNode`, before the role move changes anything (the
  Accept entry is already committed): stripping the old owner
  with no record to grant would leave no `CASE_OWNER` (CM-21-001). It reads the
  record through `listed_participant_record()`, the lookup the guard admitted it
  by, so the guards make it unreachable: an internal error, never a skip.
- **At any other replica** the sender must be the CASE_MANAGER, and a case the
  replica does not hold refuses (`SenderCheckContext.case_manager_required`,
  PCR-03-001).
- **An answer names the CASE_MANAGER's Offer by its id.** The ledgered Offer is the
  one the transferee holds, so `recorded_ownership_offer()` reads the entry by its
  `log_object_id` and follows no link (ADR-0148). Never match by time: a peer may
  claim `published` at whole seconds (ADR-0167), so two Offers can share a stamp
  and a late answer then closes the newer one (#4565).
- **Either answer closes the Offer for the other.** The Accept and the Reject share
  `OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES`, so an Accept after a Reject (or the
  reverse) is refused as "already answered".
- **Only the Case Owner's Offer is made into the CASE_MANAGER's** (CM-21-019): the
  sender guard runs before anything is written, so a stranger's Offer leaves no
  entry and no Offer, and gets no refusal notice (CLP-05-006). A
  redelivery is recognised by the Offer derived from the Owner's, whose
  `attributedTo` must be the sender, not by the role: the sender may have handed
  ownership on since (`SenderIsOfferingCaseOwnerNode`, HP-01-014).
- **At the CASE_MANAGER every `Offer(VulnerabilityCase)` is a proposal**, judged by
  the Owner-only sender rule; a participant takes the Offer from the CASE_MANAGER
  alone (CM-21-044, CM-21-019, PCR-03-001).

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
  executes a tree as the CASE_MANAGER (CM-24-011, ADR-0109). The bridge raises for
  an executing actor this container does not host (BT-05-005).
- A case always has a CASE_MANAGER (CM-02-014): when none resolves, fail; never send
  to the transferee directly (CM-24-014). The emit node raises rather than let the
  port's default address the Owner's Offer to its `target`.
- The Owner's Offer carries `context=case_id`, which the commit boundary checks
  (a `payloadSnapshot.context` that is present must name the entry's case). The
  trigger returns the Owner's Offer; the owner names it to withdraw (TRIG-11-006),
  and the withdraw trigger refuses an Offer this actor did not send.
- **The transferee travels and is stored inline**, as an `Actor` object, never a
  bare id (DL-08-003): the ledger snapshot of both Offers carries it inline
  (CLP-07-006), so the CASE_MANAGER needs no actor-profile write. The factory
  wraps a bare id (#4843).

### `MakeOwnershipTransferOfferNode`

- Builds the Offer from the validated fields only; the Owner's Offer's id, `actor`
  and `to` are not copied (CM-21-027). Its id is `ownership_offer_id()`, derived from
  the Owner's Offer and its sender, so a redelivery rebuilds the same Offer
  (OX-06-002) and another sender reusing the id names another Offer.
- Build, queue and commit run in one `transaction()`: a failed commit takes the
  queued Offer back out, so no transferee holds an Offer the ledger does not
  record (CLP-07-015, SYNC-09-002).
- Faults are not caught; they escape to `BTBridge` as an internal error, never a
  refusal of the owner (ARCH-15-001). `NoOpenOwnershipOfferNode` treats an Owner's
  Offer as a redelivery only when the Offer made from it is ledgered, so a
  redelivery after a fault makes it.

### `EmitAcceptCaseOwnershipTransferNode`

Resolve the CASE_MANAGER from the DataLayer and set `to=[case_actor_id]`; never
address the Accept to the offerer.

### `OfferCaseOwnershipTransferReceivedUseCase`

One use case and one tree (`create_propose_ownership_transfer_tree`) for both paths.
The manager path is the proposal flow above. On the participant-replica path, at the
transferee, intake keeps the CASE_MANAGER's Offer only as its
`ReceivedActivityRecord`, never under the id its sender chose (DL-06-006), and the
sender guard admits the CASE_MANAGER alone. Nothing is committed there.

- **Answer only the Offer intake archived.** The accept and reject triggers read it
  with `read_received_activity` and the adapter with `read_received_as_received`
  (the reply embeds the archived body verbatim), so an actor that never received
  the Offer gets a not-found, whatever is stored under the Offer's id (DL-06-006).
  Neither `offer_case_ownership_transfer` entry has a replay effect: the transferee
  holds the CASE_MANAGER's Offer, the owner its own, and a bystander never answers
  (ADR-0148). Do not add a ledger-derived record of either (#4911).

- **At the transferee, take the offerer from `attributed_to`, not `actor_id`**
  (#3012): the Offer is delegated, so its `actor` is the CASE_MANAGER. Honour
  `attributed_to` only on an Offer the case's CASE_MANAGER made
  (`RecordedOwnershipOffer.offerer_id`); nothing downstream re-checks it
  (CLP-07-003 checks `payloadSnapshot.actor`).
- **The snapshot builder's `_get_id` never falls back to `str(field)`**
  (`vultron/wire/as2/extractor/_builders/fields.py`): `attributedTo` may be an
  inline object or array, and a Python repr in a hashed, replicated snapshot is
  unrecoverable (CLP-07-011).

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
      2. Add(CaseLedgerEntry) → all participants.
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
  answer or withdrawal entry for it, found through `find_protocol_pair()` with
  `OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES`, or until the `end_time` the ledgered
  Offer carries passes; nothing records the expiry (CM-21-017, CM-21-043, CLP-11-001,
  ADR-0152).
- **One open Offer per case (CM-21-014).** The CASE_MANAGER refuses a new Owner's
  Offer while its own Offer is open, with a refusal notice; once closed, the owner
  may offer again to anyone, the decliner included. The check is
  `NoOpenOwnershipOfferNode` (`core/behaviors/case/nodes/ownership_offer_guard.py`,
  reading `open_ownership_offer()`) in `case_manager_admits_ownership_proposal_guard`,
  which the tree runs in an `OnPaths.at_case_manager` branch: the transferee's path
  judges nothing (HP-01-038). An Owner's Offer whose derived Offer the ledger
  already records is a redelivery: the guard sets `is_redelivery`, which it reports
  as a repeat, and the received-tree runner reports `SKIPPED` (HP-01-014,
  ADR-0195).
- **Withdrawal is an `Undo` of the Owner's own Offer (CM-21-036, CM-21-037).** The
  CASE_MANAGER derives its Offer's id from the Owner's Offer id and its own id, so
  the owner needs nothing it learned from the ledger; the ledgered Undo is a reply
  that closes the Offer.

---

## Demos

- **Address the Accept to the CASE_MANAGER and hand-deliver nothing.** A handoff
  gates on the `accept_case_ownership_transfer` entry on a **non-party** actor's
  own replica (the Reporter), since only the CASE_MANAGER's fan-out can put it
  there (CM-21-007, EDF-06-002).
  `test/architecture/test_handoff_scenarios_verify_broadcast.py` enforces this
  for **every function that calls the offer trigger**, under
  `vultron/demo/scenario/` and `vultron/demo/helpers/` alike — keyed on the
  trigger, not on a `_phase_ownership_handoff` name, because a handoff written
  as a story fragment carries no phase function and the name-keyed ratchet
  silently narrowed to one scenario when `rccv-handoff` was composed (#5535).
  The shared fragment is `owner_decision_story.the_owner_hands_the_case_over`,
  whose witness is a `Part` the caller names and defaults to the Reporter.
- **Accept the CASE_MANAGER's Offer, not the Owner's.** The CASE_MANAGER makes its
  Offer under an id it derives (CM-21-028, EDF-06-004); find it on the transferee
  with `find_ownership_transfer_offer_for_actor` and use that id in the accept
  trigger. Withdraw by the Owner's Offer id the offer trigger returned.
- **The exchange demo needs a CASE_MANAGER-owned case.** `setup_initialized_case`
  leaves no CASE_MANAGER participant; use
  `vultron.demo.helpers.workflow.setup_canonical_case`.
- **The transferee must be known to the CASE_MANAGER**: in its address book
  (`seed_peer(client, local_actor_id=case_actor_id, ...)`) and seated on its replica
  through the stub Invite (`seat_participant_through_stub_invite`), because
  a reinstatement request never seats a member (CM-31-036). While an embargo is
  active it must also have agreed to it, since only an active participant may be
  offered the case (CM-21-021). The commit boundary no
  longer catches a transferee sent by bare id: a snapshot records `target` as sent
  (CLP-07-006), so the inline `Actor` the factory builds is what every replica
  reads.
- **The exchange demo drives every step through its actor's trigger**
  (DEMOMA-05-001): the vendor's `offer-case-ownership-transfer`, then the
  coordinator's `accept-` or `reject-case-ownership-transfer`. It gates on the
  CASE_MANAGER's ledger entries (`offer_case_ownership_transfer`,
  `reject_case_ownership_transfer`), not a timed read (EDF-06): the reject path's
  "owner unchanged" check means nothing until the Reject is known processed.
