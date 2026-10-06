---
status: accepted
date: 2026-09-29
created: 2026-09-29
updated: 2026-09-29
revision: 1
deciders: Allen D. Householder
consulted: >-
  notes/bt-integration.md, notes/case-ledger-authority.md,
  specs/case-ledger-processing.yaml,
  docs/adr/0022-single-bt-execution-for-received-side-case-actor-routing.md,
  docs/adr/0107-case-ledger-entry-is-a-postmark-on-the-received-envelope.md,
  issue #3339
informed: CERT/CC Vultron protocol team
stakeholder_type: [project-contributor]
---

# Intake Is the First Stage of a Received-Side Tree: Record What Arrived Before Judging It

## Context and Problem Statement

A received-side use case runs one behavior tree, and that tree has three named stages in a fixed order: precondition guards, the guarded ledger commit, and protocol effects (ADR-0022, CLP-10-006).
The ordering rule classifies any node that writes to the DataLayer as a protocol effect, so it must follow the commit.

Storing the received activity, and the objects the sender inlined in it, is a write.
Under the rule it belongs after the commit.
But several handlers need that record whether or not the assertion is later accepted.
A receiver that has case auto-creation switched off, or that is not the primary recipient of an Offer, must still keep the report and the Offer for a later acknowledgement or an explicit decision (CM-15-002).
An invitee must keep the Invite and the sender's identity as a trust anchor before it holds any case at all (PCR-03-004).

The codebase resolved the contradiction by stepping outside the tree.
Eleven received-side `execute()` bodies in nine files reach a DataLayer write through helper functions before any tree runs: most store the inbound object, and two store the participants inlined in an inbound case.
The mutation ratchet that guards `execute()` matches only a write whose receiver is literally the use case's DataLayer inside the method body, and excludes helpers by design, so none of them is a violation it can see (issue #3339).
Two more handlers, add-report and remove-note, mutate the case directly with no tree at all.

The pipeline has no name for "record what arrived".
What are the received-side stages, and where does storing the received activity belong?

## Decision Drivers

- **Receipt is a fact; acceptance is a verdict.** The case ledger records accepted assertions and never a refusal (CLP-04-007, CLP-05-002). The receiver still received the message, and its own record of that must not depend on the verdict.
- **The ledger is a postmark on the received envelope** (ADR-0107). The commit records the received activity, not a reconstruction of it, and a replica resolves a bare reference by dereference. Both need the receiver to hold what arrived, exactly as it arrived.
- **Everything protocol-significant lives in the tree** (BT-06-001, CLP-10-005). A write reached from `execute()` through a helper is outside the tree, whatever it is called.
- **One implementation, not many.** Storing the received activity is the same act for every message type. DRY is a project standard (CS-22-001).

## Considered Options

1. **Intake is a mandatory first stage, before the guards.** The shared tree factory always runs one shared intake node first. It stores the received activity and its inlined objects verbatim and idempotently, decides nothing, and is not a protocol effect. Guards, commit, and effects follow unchanged.
2. **Keep three stages; preserve store-even-when-refused through tree structure.** Each tree that needs the record on a refusal places a store node inside the refusing arm of a Selector. No spec change.
3. **Leave intake storage as procedural glue in `execute()`** and enumerate the nine files as permanent ratchet exemptions.

## Decision Outcome

Chosen option: **"Intake is a mandatory first stage, before the guards"**, because it is the only option that states what the code already needs to do, does it once, and keeps every write inside the tree where the ratchet can see it.

### Decision details

1. **Four stages.** A received-side tree runs intake, then precondition guards, then the guarded commit, then protocol effects (CLP-10-006, CLP-10-010 as amended).
2. **Intake records receipt.** The intake node idempotently stores the received activity and every object inlined in it, exactly as received. It interprets nothing, gates nothing, and ledgers nothing (CLP-10-017). It is not a protocol effect, so the ordering rule's definition of that class excludes it.
3. **Intake is uniform and mandatory.** `create_receive_activity_tree` supplies the intake node as the first child of every tree it builds. No handler opts out, because receipt is a fact for every message.
4. **A refusal leaves intake in place.** A precondition guard that refuses the assertion does not remove or alter what intake stored (CLP-10-018). The refusal goes to the process log and, where the protocol calls for it, a Reject to the sender.
5. **Intake is the only store path.** No handler-local helper, per-tree store node, or call in `execute()` may store the received activity or its objects (CLP-10-019). The shared idempotent-create helper in the use-case layer and the per-domain store nodes it fed are retired in favour of the intake node. The routing-level `auto_create_case` short-circuit that CM-15-005 allowed in the submit-report handler is retired with them, because it existed to store the report and Offer before the tree ran; CM-15-005 is amended to require the in-tree condition node.
6. **The ratchet follows helpers.** The mutation ratchet treats a DataLayer write that `execute()` reaches through any function or method defined under the use-case package, transitively, as a violation of that `execute()` (CLP-10-020). Writes inside BT nodes are not violations, so resolution stops at the package boundary.
7. **Every receive tree composes through the factory.** The two receive trees that compose `create_case_manager_gated_tree` directly today, `create_add_note_to_case_received_tree` and `create_update_case_received_tree`, move onto `create_receive_activity_tree` so that "no handler opts out" holds by construction and the ordering ratchet can assert factory coverage (#3870).

### Consequences

- Good, because the receiver's record of what arrived no longer depends on the verdict, which is what CM-15-002 and the invitee trust anchor already required.
- Good, because the procedural store sites and the shared helper behind them collapse into one node, composed once.
- Good, because the intake record is the natural home for the received evidence ADR-0107 seals at parse. Step 5 of that ADR persists the evidence for deferred replay; intake is where that persistence happens (see the amendment: the objects a later entry names by reference are recovered from that evidence, not from records intake wrote).
- Good, because a handler-local write can no longer hide from the ratchet behind a helper name.
- Bad, because every existing tree the factory builds changes shape, the two receive trees that bypass the factory today must be moved onto it, and the ordering ratchet, the intake node, and the widened mutation ratchet must land before the handlers can migrate.
- Bad, because intake stores every received activity, including ones a guard refuses a moment later. Storage grows with traffic the receiver declines. This is the cost of treating receipt as a fact, and the process log already recorded these arrivals; the DataLayer now does too.

## Validation

- `test/architecture/test_receive_side_intake_first.py` asserts every receive-side tree factory returns the shared factory's result, so the intake node is its first child, ahead of every guard and the commit.
- `test/architecture/test_no_dl_mutations_in_execute.py` resolves DataLayer writes through use-case-layer helpers transitively and holds the remaining violations as an exact set. The set empties as the handlers migrate.
- A refused assertion leaves the received activity and its inlined object readable from the receiver's DataLayer, asserted per handler.

## Pros and Cons of the Options

### Intake is a mandatory first stage, before the guards

- Good, because it names the stage the code already has and makes the ordering rule true rather than routinely bypassed.
- Good, because one node replaces the per-handler helpers and the ratchet sees it.
- Bad, because it is a spec amendment plus a change to every existing tree.

### Keep three stages; preserve store-even-when-refused through tree structure

- Good, because no spec changes.
- Bad, because each tree that needs the record on refusal solves the same problem again with its own Selector plumbing, and a new handler can forget.
- Bad, because a store node inside a refusing arm is still a DataLayer write before the commit, so the ordering rule is violated in a way the structural test cannot see.

### Leave intake storage as procedural glue in `execute()`

- Good, because nothing moves.
- Bad, because it contradicts the single-tree contract (CLP-10-005) that ADR-0022 set, and keeps nine permanent exemptions in a ratchet whose purpose is to reach zero.
- Bad, because the sites differ in detail, so "glue" would have to be defined by enumeration rather than by rule.

## Amendment — 2026-09-30

Building the intake node (#3870) overturned three premises above, and the decision is amended rather than superseded because its core — intake first, before any guard — stands.

**Intake archives the mail, not the letter's contents.**
Detail 2 said intake stores "every object inlined" in the activity.
That treated an inlined case, note or status as core's record of that object.
It is not: it is a message shaped like the object, and the record core keeps is written by an effect node from the copy the event carries, after the guards.
Writing the inlined objects at intake would let any sender seed a case replica ahead of the trust checks (PCR-03-004, CBT-01-005), because a stored case row *is* the actor's Participant Case Replica, and the same holds for a `CaseLedgerEntry` inlined in the replication envelope.
So intake archives the received activity only, exactly as received, and CLP-10-017, CLP-10-018 and CLP-10-019 now say so.
The stored `VultronActivity` dehydrates `object` and `target` to ids, so the faithful copy of what arrived is the received evidence ADR-0107 seals at parse; #3742 persists it beside the archived row, and the intake node is where.
Detail 5 stands with the correction that the handler-local helpers are replaced by effect nodes that write the core record from the copy, not by intake storing it (#3871–#3874 re-scoped accordingly).

**Fifteen trees bypassed the factory, not two.**
Detail 7 assumed the two trees composing the CASE_MANAGER gate directly were the only ones outside `create_receive_activity_tree`.
Defining a receive-side tree as one a received use case calls, the ordering ratchet found fifteen.
They are held as an exact set (`KNOWN_FACTORIES_BYPASSING_INTAKE`, ARCH-18-001) and each moves with the handler migration that owns its area; the sync announce and reject trees and the dead-letter tree moved in #3935.
`create_commit_log_entry_tree` is not a receive-side tree: it is the subtree the commit node runs, and no received use case calls it, so it is outside the ratchet's definition.

**The commit stage needs a canonical signature.**
CLP-10-013 required every factory-built tree to pass `case_id` and commit.
`Update(VulnerabilityCase)` has no canonical payload signature, so the CASE_MANAGER refused its own commit the moment the update tree moved onto the factory.
CLP-10-013 is amended to require the commit exactly when the received `(type, object)` pair is a canonical signature; the update tree and the sync trees pass `case_id=None`.

**An owner's `Update(VulnerabilityCase)` is not a ledgered assertion (#3936).**
ADR-0108 says case state flows through the case manager and the ledger, and the ledger carries completed acts (ADR-0119).
An `Update(VulnerabilityCase)` is neither: the message is a request to change case fields that no production code sends (`update_case_activity` is called only by the vocabulary examples), it has no story in the protocol's use cases, and its one visible effect, the CM-06-001 broadcast, duplicates what `Announce(CaseLedgerEntry)` fan-out already does for every ledgered change.
Making it canonical would add a signature, a replica apply slot and changed entry hashes in every demo, for a message nobody emits.
So it stays outside `_CANONICAL_PAYLOAD_SIGNATURES`; `create_update_case_received_tree` passes `case_id=None`; a receiver applies it to its replica and only the CASE_MANAGER announces it (CM-06-001).
A case change an actor wants ledgered is made by a canonical act, not by this message.
The received path is kept because the wire vocabulary still defines the activity; removing the vocabulary, the semantic and the handler together is a protocol-surface change left to its own decision.

**The archive is keyed by the receiver, not by the sender.**
The first build archived the activity as its own row, under the id the sender chose, which treated the archive as inert.
It is not: the DataLayer is one id-keyed table per actor, so a sender who names its activity after a record the receiver derives (a pending-case-inbox marker, an offer record, a report-case link) occupies that id ahead of the receiver's own write, the later `create()` fails as a duplicate, and a read-then-create helper reads the squatter as "already stored".
The same exposure already existed through the pre-tree store helpers; intake would have extended it to every received tree from any sender.
So intake writes a `ReceivedActivityRecord` whose id the receiver derives (`ReceivedActivityRecord.build_id`), carrying the sender's id as data for the reverse lookup and the activity whole; a sender's choice of id can now collide with nothing but its own earlier delivery.
A record the receiver keeps is the receiver's to key; the sender's identifier is content, never the address.
CLP-10-017 says so; the handler migrations that still store under the sender's id (`KNOWN_VIOLATIONS`, #3871–#3874) retire that shape as they move onto intake, and a reader that needs the archived activity goes through `build_id`.

## More Information

- [ADR-0022](0022-single-bt-execution-for-received-side-case-actor-routing.md) set the single-tree contract and the guards, commit, effects ordering this record extends with a stage in front.
- [ADR-0107](0107-case-ledger-entry-is-a-postmark-on-the-received-envelope.md) decides what the commit records and how a replica resolves a reference. Intake is where the receiver keeps what arrived so both are possible.
- [ADR-0019](0019-separate-case-ledger-from-process-log.md) separates the case ledger from the process log. Intake writes to neither; it writes the receiver's own record of receipt.

Generated spec requirements: `case-ledger-processing.yaml` CLP-10-006 and CLP-10-010 (amended), CLP-10-017 through CLP-10-020; `case-management.yaml` CM-15-005 (amended).

Source: ISSUE-3339.

## Annotation — 2026-10-02

The amendment of 2026-09-30 was made without a human reviewing it.
The 2026-10-02 audit (#4195) confirmed sealed-at-emission and byte-for-byte relay (OX-07 as rewritten) and recorded that the receive-side verbatim snapshot is a defect to finish (#3742): the "faithful copy of what arrived" the amendment names is not yet persisted beside the archived row.
The commit-stage carve-out for `Update(VulnerabilityCase)` (CLP-10-013) stays with #3936.
Reviewed by Allen D. Householder, 2026-10-02.
