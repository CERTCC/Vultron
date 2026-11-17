---
status: accepted-provisional
date: 2026-11-17
created: 2026-11-17
updated: 2026-11-17
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0111, ADR-0135, ADR-0151, ADR-0154 (the records this one
  consolidates); ADR-0022, ADR-0095, ADR-0141, ADR-0146, ADR-0149, ADR-0153,
  ADR-0155; specs/case-ledger-processing.yaml CLP-10; specs/handler-protocol.yaml
  HP-01; specs/inbox-endpoint.yaml IE-10; specs/sync-ledger-replication.yaml SYNC-14
informed: []
supersedes:
  - 0111-intake-is-the-first-received-side-stage.md
  - 0135-compose-received-trees-never-chain-them.md
  - 0151-a-received-act-commits-its-own-entry-with-its-consequences.md
  - 0154-a-received-message-is-one-staged-record-archived-only-when-applied.md
stakeholder_type: [project-contributor]
---

# A Received Delivery Is One Tree in Fixed Stages, and Its Outcome Decides What Is Kept

## Context and Problem Statement

A received-side use case runs one behavior tree for each inbox delivery (ADR-0022).
Four records then decided what that tree runs, in what order, and what the receiver keeps of the message.
ADR-0111 put intake first and archived every arrival.
ADR-0135 made every delivery one tree, counted through helpers, and added a clock-decision stage.
ADR-0151 made the received act's own commit and its effects one transaction.
ADR-0154 moved the door checks ahead of intake and kept a refused message only as a receipt stub.

Each later record replaced part of an earlier one, so the rule as it stands could be read only by laying the four over each other.
ADR-0111's central choice, intake first, no longer held.
One of its amendments, that `Update(VulnerabilityCase)` is not a ledgered assertion, had also been overtaken: the ownership transfer made that pair a canonical signature.

This record states the four decisions as one.
It decides nothing they did not.

What does a received delivery run, in what order, and what does the receiver keep of it?

## Decision Drivers

- **Logic outside a tree is invisible.** The decision to run a step belongs in the tree, where the ratchets and a reader can see it (ADR-0022, BT-06-001). Two trees that must both run are one tree that has not been written yet.
- **Receipt is a fact; acceptance is a verdict.** The receiver must be able to say what it received, from whom, when, and why it declined it, whatever the verdict (CLP-04-007, CLP-05-002).
- **A message not for the receiver is not the receiver's record** (HP-01-005, HP-10-001). An early answer must spare the later work and the write.
- **The archive is the received body as the parser sealed it** (ADR-0107, ADR-0149).
- **A sender's content must not seed the receiver's records ahead of the trust checks** (PCR-03-004, CBT-01-005).
- **An act succeeds or fails as a whole.** No repair pass, later run or redelivery finishes an act (ADR-0146). A received act and a trigger act follow the same rule.
- **A crash must not lose a message, nor apply it twice.**
- **A sender with no standing must never make the CASE_MANAGER write** (HP-01-006).

## Considered Options

1. **One tree in fixed stages: cheap doors first, then one staged record, one atomic act, and an outcome stage that decides what is kept.**
2. **Intake first: archive every arrival before any check, and keep the refused ones.** This was ADR-0111's choice, as built.
3. **Several trees per delivery, chosen and sequenced by Python in the use case.** This was the drift that ADR-0135 found in about fifteen handlers.
4. **Commit the received activity's entry durably on its own, and apply its change again when the effects roll back.**

## Decision Outcome

Chosen option: **"One tree in fixed stages"**.
It is the only option under which every delivery is one tree that a reader can see whole, an early answer prevents the write, receipt stays a fact for every message, and a received act is atomic without recovery machinery.

### Decision details

1. **One tree per delivery, counted through helpers.**
   A received-side `execute()` builds one tree and runs it once (CLP-10-005, CLP-10-028).
   A tree run, or a DataLayer write, that `execute()` reaches through any function under the use-case or service packages counts as its own (CLP-10-005, CLP-10-020).
   Door checks, clock decisions, refusals and alternative branches are nodes, guards and selectors that the tree's factory composes.
   Python control flow in a use case does not choose between trees or run one after another (CLP-10-029).
   An alternative answer that replaces the commit, such as the answer to a late embargo `Accept`, is a diversion among the precondition guards (CLP-10-026).

2. **The stages run in a fixed order, and every stage can end the run.**
   1. The door guards: the addressee check (HP-01-005), the seen-before door (detail 9), the path stage (ADR-0153), the post-close write boundary (CM-23-013), the closed-sender door (CM-23-018) and the sender guard (HP-01-006).
   2. Intake (detail 3).
   3. The ledger-position answer (ADR-0155).
   4. The clock decisions (detail 5).
   5. The precondition guards, with any diversions.
   6. The commit of the received activity's own entry (detail 4).
   7. The protocol effects.

   The doors only read, so nothing is written before intake, and a message a door rules out costs one read and one receipt stub (CLP-10-010).
   The post-close boundary sits beside the sender guard, because whether a closed case takes the write is a question about the case, asked once the message is known to be for the receiver.

3. **Intake writes the message's one staged record, and nothing else.**
   The record holds the received body as the parser sealed it, under an id the receiver derives (`ReceivedActivityRecord.build_id`), with the sender's activity id kept as data (CLP-10-017, CLP-10-036).
   A record the receiver keeps is the receiver's to key, so a sender's chosen id can collide with nothing but its own earlier delivery.
   Intake writes no core record from an object inlined in the activity (CLP-10-038).
   An inlined case, note or status is a message shaped like the object, and storing it at intake would let any sender seed a case replica ahead of the trust checks.
   An effect node writes the core record after the guards, from the copy the event carries (CLP-10-039).
   Intake is the only path that stores the received body (CLP-10-019).
   The record stays in holding while the message is judged, and rests only where time can pass: waiting for its case, for a ledger gap to fill, or for a local decision.

4. **The commit records the received activity when its `(type, object)` pair is a canonical signature.**
   The CASE_MANAGER then commits one canonical ledger entry for each admitted activity (CLP-10-013).
   A tree whose activity has no canonical signature has no commit stage (CLP-10-033).
   A canonical activity that only the CASE_MANAGER sends, and only a participant replica receives, has none either, because its entry is committed where the CASE_MANAGER sends it (CLP-10-034).

5. **A clock decision is the CASE_MANAGER's own act, ahead of the guards.**
   An expiry must be ledgered whether the activity that revealed it is then admitted or refused, and before a guard that depends on it judges that activity.
   A new ownership Offer that arrives after the open one's deadline is the example: the expiry must close the old Offer before the one-open-Offer guard can admit the new one.
   So a clock decision runs only at the CASE_MANAGER, and commits only the CASE_MANAGER's own entries and the case-file changes they record, one entry for each AS2 activity it needs (CLP-10-050, CLP-10-052).
   It takes its evidence from the CASE_MANAGER's clock, its local policy and the case's ledger and file, never from the received activity, which may only prompt it (CLP-10-054, CLP-10-055).
   One with nothing to record succeeds; one whose commit the ledger refuses logs a warning and does not end the tree, because the guards still refuse what the unrecorded decision forbids; an internal error ends the tree as an internal error (CLP-10-057 to CLP-10-060).
   The embargo end-time check is a decision about the case, not about one activity, so every received tree that names a case and has both the sender guard and the post-close boundary takes it, and no dispatcher hook runs it ahead of the tree (CLP-10-051).
   A case-scoped trigger composes the same CASE_MANAGER-gated stage as the first step of its own tree, so that it does not act on an embargo whose end has passed (BT-15-003).

6. **A refusal commits nothing, and may answer the sender.**
   The factory adds the refusal notice, a `Reject` of the refused activity, as the first refusal effect of every tree that commits to a case (ADR-0141, CLP-10-022).
   A tree passes any further answer it owes as `refusal_effects`; they run only when a precondition guard refuses, only at the CASE_MANAGER, and never for a door's refusal, a repeat, a diversion or a redelivery (CLP-10-041 to CLP-10-044, CLP-10-070).
   A refusal effect only emits; the CASE_MANAGER's own note is the one exception, and commits itself as its own entry (CLP-10-048).
   The tree still fails with the guard's refusal, and the handler reports `REFUSED` for the guard's reason (CLP-10-046).

7. **The commit and the effects are one act.**
   In a tree whose effects commit consequences of the act, the commit, the replica effects and the CASE_MANAGER effects run as one `ActTransaction`, inside one DataLayer transaction (CLP-07-015).
   When any of them fails or raises, nothing any of them wrote is kept, so no entry stands without its consequences.
   The act block is the same at every receiver: at a participant replica the commit gate skips, and a failing replica effect keeps none of the replica effects' writes.
   The intake record, a clock decision and a refusal are outside the act, so an act's rollback leaves them in place.
   Whether the doors and guards join the act's transaction too is open (#6402).

8. **The outcome decides what the receiver keeps.**
   One outcome stage, outside the handling tree and after it, maps the handler's verdict onto the record's final stage (CLP-10-073).
   - Applied or skipped: the record keeps its sealed body and moves to the archive.
   - Refused: the record becomes a receipt stub under the same key, holding the sender, the sender's activity id, the time of receipt, the refusal reason and the digest of the body, and no body (CLP-10-018, CLP-10-075).
   - Deferred: the record stays in holding as the wait left it.
   - No verdict, because the dispatch raised or returned no result: the record stays in holding with its sealed body (CLP-10-074).

   A refused message's body is kept only in the process log.
   A message waiting for its case, a duplicate and a crash recovery all use this one record, not three mechanisms.
   An addressed `Offer(Report)` takes the ordinary order; declining to create a case is still an applied outcome, so the report is archived and CM-15-002 holds, while a `cc`-only copy is refused at the addressee door (HP-10-001).

9. **A resend is answered from what was recorded.**
   A resend whose digest matches a receipt stub is `REFUSED` again with the stub's reason, and nothing is re-run: a refusal is whole and final for that activity.
   A resend whose digest differs from what the receiver holds is refused as a reused id (IE-10-002).
   A resend of an applied message, or of one still in holding, is `SKIPPED`, and no refusal notice is sent again.

10. **A failed act is answered with a fault, and runs again from the held body.**
    A child that raises is an internal error: the act rolls back, and the record stays in holding.
    The inbox answers the sender with one `Create(ProcessingFault)` of the internal-error class, sent after the rollback, with no diagnostics, and with an id derived from the activity and the failure class, so a second failure builds no second fault (ASK-07-006, ASK-07-010).
    A fault whose own handling fails is not answered with another.
    A later delivery of the activity, or a re-run, runs the act with the held body, never with the later delivery's body; a redelivery of an act that committed is `SKIPPED`.

11. **A run starts over; it never resumes partway.**
    A message whose run ended with no verdict is run again from its door guards (CLP-10-083).
    Each stage boundary hands over one named input, and a stage reads nothing else an earlier stage left in memory (CLP-10-082, CLP-10-084).
    The handling tree takes the path from the path stage and does not read the role again, because an act such as an ownership transfer changes who the CASE_MANAGER is partway through the run.
    Every handling tree must tolerate a re-run after a crash; the once-per-act commit and the derived-id sends (SYNC-09-002, OX-06-002) provide it, and each tree is tested for it.

12. **A held ledger entry is replayed as the `Announce` that carried it.**
    A participant holds the `Announce(CaseLedgerEntry)` it received, as the body that arrived, never the entry alone (SYNC-14-001).
    When a commit or a case seed makes that entry appliable, the receiver replays the held `Announce` through its own inbox as a delivery of its own (SYNC-14-009).
    It does not run the entry's tree inline or in a nested bridge run, and it builds no activity that nobody sent.

### Consequences

- Good, because every received delivery is one tree that the ordering, intake, gate and mutation ratchets inspect whole.
- Good, because a message that is not for the receiver costs one read and one stub, not a permanent copy.
- Good, because receipt is still a fact for every message: the stub records who sent what, when and why it was declined, and its digest detects a reused id without the body.
- Good, because a received act and a trigger act follow one rule, and no committed entry exists without its consequences.
- Good, because an expiry is ledgered whether the activity that revealed it is then admitted or refused.
- Good, because waiting, duplicate detection and crash recovery share one record.
- Bad, because a refused message's body is not kept, so evidence of what a misbehaving sender sent is only in the process log.
- Bad, because the act's transaction holds the store's write lock for the commit and every effect, so another writer on the same store waits longer.
- Bad, because the fault tells the sender only that processing failed, not why, so it cannot tell a transient failure from one that will repeat.
- Bad, because every handling tree must be shown to tolerate a re-run, and a new tree carries that obligation.

### Confirmation

- `test/architecture/test_single_bt_execution_received_side.py` counts tree runs through helpers.
- `test/architecture/test_no_dl_mutations_in_execute.py` counts DataLayer writes through helpers.
- `test/architecture/test_receive_side_staged_order.py` and `test/core/behaviors/case/test_receive_activity_tree.py` pin the stage order, the clock-decision stage's gate and failure behaviour, the refusal effects and the act block.
- `test/architecture/test_received_stages_read_the_record.py` fails a handling-tree node that reads a door stage's in-memory state other than the path.
- `test/adapters/driving/fastapi/test_received_outcome_stage.py` and `test/adapters/driving/fastapi/test_seen_before_door.py` drive each outcome and each kind of resend.
- `test/adapters/driving/fastapi/test_failed_act_redelivery.py` and `test/core/behaviors/test_act_transaction.py` show a failed act keeps nothing, is answered with one fault, and runs again from the held body.
- `test/adapters/driving/fastapi/test_interrupted_run_restart.py` re-runs an interrupted delivery from its doors.
- `test/core/use_cases/triggers/embargo/test_end_time_termination.py` shows a non-participant's activity commits no termination, and a case-scoped trigger ends an overdue embargo before it acts.

## Pros and Cons of the Options

### One tree in fixed stages

- Good, because the order of the questions does the work: an early answer ends the run before anything is stored.
- Good, because one record replaces the holding record, the duplicate re-run and the in-memory intake flags.
- Good, because the act is atomic, so nothing has to repair it.
- Bad, because every tree and the stored shape of a refused message had to change.

### Intake first, and keep every arrival

- Good, because receipt is recorded before anything can go wrong.
- Bad, because the receiver keeps, permanently, the content of every message it declined, including copies never addressed to it.
- Bad, because the doors run after the write, so an early answer spares nothing.
- Bad, because waiting, duplicates and recovery stay three mechanisms.

### Several trees per delivery, chosen by Python

- Good, because no handler has to move.
- Bad, because the cascade it builds is the one ADR-0022 rejected: the logic that chooses between trees is invisible to analysis and audit.
- Bad, because each new clock-driven step would ask for another exception.

### Commit durably on its own, and re-apply after a rollback

- Good, because the commit is durable as soon as it runs.
- Bad, because it leaves an entry committed without its consequences, a state no single act produces.
- Bad, because the re-apply is recovery machinery that cannot recreate the consequences: a received proposal whose relay failed stayed in the register with no consent rows, and its redelivery was refused.

## More Information

This record supersedes, whole:

- [ADR-0111](archived/0111-intake-is-the-first-received-side-stage.md): intake as a stage, its single store path, the helper ratchet, and the receiver-derived key are details 1, 3 and 4 here; its intake-first order is replaced by detail 2, and its archive of every arrival by detail 8.
- [ADR-0135](archived/0135-compose-received-trees-never-chain-them.md): one tree per delivery and compose-never-chain are detail 1, the clock-decision stage is detail 5, and the drained entry, as its 2026-10-21 amendment left it, is detail 12.
- [ADR-0151](archived/0151-a-received-act-commits-its-own-entry-with-its-consequences.md): the act block is detail 7 and the internal-error fault is detail 10.
- [ADR-0154](archived/0154-a-received-message-is-one-staged-record-archived-only-when-applied.md): the order of questions is detail 2, the staged record and its outcomes are details 3 and 8, the resend rules are detail 9, and the run that starts over is detail 11.

Not carried forward, because it had been overtaken before this record: ADR-0111's carve-out that `Update(VulnerabilityCase)` has no canonical signature, its list of trees bypassing the factory, and its migration notes; and ADR-0135's wrapped `Announce`, which its own amendment had replaced.

Related:

- [ADR-0022](0022-single-bt-execution-for-received-side-case-actor-routing.md) set the one-tree contract.
- [ADR-0095](0095-received-side-handler-result.md) defines the handler verdict the outcome stage reads.
- [ADR-0141](0141-a-refused-assertion-is-answered-with-a-reject-of-the-refused-activity.md) decides the refusal notice.
- [ADR-0146](0146-one-atomic-commit-per-case-manager-act.md) decides that an act commits all at once.
- [ADR-0149](0149-the-received-archive-is-the-sealed-received-body-read-through-a-read-only-view.md) decides that the archive is the sealed received body.
- [ADR-0153](0153-one-role-check-per-message-picks-the-received-path.md) decides the path stage.
- [ADR-0155](0155-a-participant-states-its-ledger-position-and-the-case-manager-answers-a-lag.md) decides the ledger-position answer.
- [ADR-0207](0207-a-tree-has-a-fixed-shape-and-every-act-runs-one.md) (proposed) extends one tree per delivery from the use case down into the nodes.
- #6402 asks whether the whole delivery, doors and guards included, runs in one transaction.

Requirements: `case-ledger-processing.yaml` CLP-07-015 and CLP-10; `handler-protocol.yaml` HP-01-005, HP-01-012 and HP-10-001; `inbox-endpoint.yaml` IE-10; `sync-ledger-replication.yaml` SYNC-14-009; `behavior-tree-integration.yaml` BT-15-003.
