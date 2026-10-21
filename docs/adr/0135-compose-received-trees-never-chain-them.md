---
status: accepted-provisional
status_override: >-
  The maintainer chose on 2026-10-15, in the ISSUE-4641 decisions recorded on
  the issue during the Epic #4638 run, to revise ADR-0135 in place as
  revision 2: detail 4 counts a clock decision's entries by the AS2
  activities it needs, and detail 5 adds the case-wide end-time decision with
  its trigger scope note.
date: 2026-10-14
created: 2026-10-14
updated: 2026-10-21
revision: 3
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0022; ADR-0111; specs/case-ledger-processing.yaml
  CLP-10; specs/sync-ledger-replication.yaml SYNC-14; issue #4585
informed: []
partially_superseded_by:
  - 0154-a-received-message-is-one-staged-record-archived-only-when-applied.md
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0111-intake-is-the-first-received-side-stage.md
---

# Compose Received Trees, Never Chain Them

## Context and Problem Statement

ADR-0022 decided that a received-side use case runs one behavior tree per inbox delivery, and its architecture test counts `execute_with_setup()` calls written directly in `execute()`.
Helpers are not counted, so the rule has drifted one call down.
An audit for issue #4585 found about fifteen received handlers that run more than one tree per delivery through helpers.
They fall into five patterns:

- **Door checks** run as one-node trees before the main tree: the sender, post-close and repeat-answer guards.
- **Clock decisions** run as their own trees before the main tree: the ownership-transfer Offer expiry and the embargo Invite expiry.
- **Refusals** are chosen by Python from several refusal trees.
- **Alternative branches** are chosen by Python: the P/X/A refusal and the late-Accept routing of an embargo Invite answer.
- **Follow-ups** run after the main tree: the gap-buffer drain that applies parked ledger entries.

An embargo Invite Accept can run five trees in a row, with Python choosing between them.
That is the cascade ADR-0022 rejected as Option B, because logic outside a tree is invisible to analysis and audit.

One of the five does not fit ADR-0111's four stages.
The CASE_MANAGER must ledger an expiry before it judges the activity that revealed it, and also when it then admits that activity.
Take a new ownership Offer that arrives after the open Offer's deadline has passed.
The expiry entry must close the old Offer before the guard that allows one open Offer at a time can admit the new one.
ADR-0111 commits nothing before the guards, so the expiry was moved into a tree of its own.

## Decision Drivers

- Behavior trees exist to be composed: two trees that must both run are one tree that has not been written yet.
- The decision to run a step belongs in the tree, where the ratchets and a reader can see it (ADR-0022).
- An expiry must be ledgered whether the prompting activity is then admitted or refused (CLP-07-013, CM-21-014, CM-21-017).
- A sender with no standing must never make the CASE_MANAGER write (HP-01-006).
- A nested bridge run can hide an internal error in the inner tree.

## Considered Options

- Compose every received delivery into one tree, with a clock-decision stage and an inbox hand-back for drained entries
- Amend the one-tree rule with named exceptions for the expiry trees
- Keep four stages and write the expiry as a refusal effect

## Decision Outcome

Chosen option: **"Compose every received delivery into one tree"**, because it is the only option under which every received delivery is one tree that the ratchets and a reader can see, and the one that handles an expiry whose prompting activity is then admitted.

### Decision details

1. **One tree per delivery, counted through helpers.** A call to `execute_with_setup()` that `execute()` reaches through any use-case-package function counts as its own (CLP-10-005).
   This is the same transitive rule the mutation ratchet already applies to DataLayer writes (ADR-0111 detail 6).
2. **Compose, never chain.** Door checks, refusals and alternative branches become nodes, guards, refusal effects and selectors inside the one tree, built by its factory.
   Python control flow in a use case does not choose between trees or run one after another.
3. **A clock-decision stage.** The received tree gains a stage between the door guards and the precondition guards.
   The order is: intake, then door guards (post-close boundary, addressee check, sender guard), then clock decisions, then precondition guards, then the guarded commit, then effects (CLP-10-010).
   This partially supersedes ADR-0111 detail 1, whose four stages put no commit ahead of the guarded commit: the CASE_MANAGER's own clock decisions are the one exception.
4. **The stage is narrow.** A clock decision runs only at the CASE_MANAGER and commits only the CASE_MANAGER's own entries and the changes they record, never anything about the received activity.
   A case ledger entry is one AS2 activity and its object, and the CASE_MANAGER does only what AS2 activities can express, ledgering each one.
   So a clock decision commits one entry for each AS2 activity needed to express what it decided, with no fixed count: an expiry is one entry, and an embargo's end-time termination is the `Remove` plus each status update and re-issued stub Invite it needs.
   The entries are ordered so that no prefix of them leaves the embargo register showing an entry terminated while another is still proposed (EP-08-004, ADR-0122): the `Remove` carries the whole register step, the cancellation of every open proposal included.
   It decides from the CASE_MANAGER's clock, its local policy and the case's ledger and file.
   The received activity may prompt it, but is never its evidence.
   The entry may still carry the activity's claimed `published` time as received, because that time records when the activity claims to have been sent and decides nothing.
   One with nothing to record succeeds.
   One whose commit the ledger refuses logs a warning and does not end the tree, because the guards still refuse what the unrecorded decision forbids (CLP-10-025).
   An internal error still ends the tree as an internal error (ADR-0095).
5. **A decision about the case runs whatever the entry point.** The embargo end-time check (EMB-13-003) is a fact about the case, not about any one activity, so it is a clock decision of every received tree that names a case and has both door guards, with no argument from the tree.
   A tree with no sender guard takes it once it declares its sender rule (each handler still exempt from a sender check names the open issue that declares its rule), because the decision writes and a sender with no standing must never make the CASE_MANAGER write.
   A tree exempt from the post-close boundary never takes it.
   The check runs in no dispatcher hook ahead of the tree.
   Scope note: this record governs received trees, but the same reason holds for a case-scoped trigger, which composes the same CASE_MANAGER-gated stage as the first step of its own one tree (BT-15-003).
   Without it, a trigger such as accepting a pending revision would extend an embargo whose end time has passed.
   The terminate-embargo trigger is the exception, because its own tree takes the end-time path and answers for it.
6. **A drained entry is its own delivery.** When a commit or a case seed makes a buffered ledger entry appliable, the receiver hands the entry back to its own inbox processing, under the receiving actor, as a delivery of its own (SYNC-14-009).
   The buffer holds the entry, not the Announce that carried it, so the hand-back wraps it in an Announce attributed to the case's CASE_MANAGER.
   It does not run the entry's tree inline, and it does not nest a bridge run inside a node.

### Consequences

- Good, because every received delivery is one tree that the ordering, intake, gate and mutation ratchets can inspect whole.
- Good, because the expiry, the late-Accept routing and the refusals become visible tree structure instead of Python branches.
- Good, because the drain no longer attributes an entry to a sender it guessed (the case id when no CASE_MANAGER is found): a handed-back entry comes from the CASE_MANAGER and runs the same inbox path as any delivery.
- Bad, because about fifteen handlers must be migrated, and the shared factory grows a stage.
- Bad, because the hand-back needs a new driven port and an adapter for the actor's own inbox.
- Neutral, because the gap buffer stays in memory, so a restart loses parked entries exactly as it does today.

## Validation

`test/architecture/test_single_bt_execution_received_side.py` counts tree runs through helpers with no exemption set.
`test/core/behaviors/case/test_receive_activity_tree.py` pins the clock-decision stage's position, gate and failure behaviour.
`test_receive_side_bt_commit_ordering.py` accepts a commit ahead of the guards only inside that stage, and there only from the decision's own CASE_MANAGER commit nodes.
`test/core/use_cases/triggers/embargo/test_end_time_termination.py` shows a non-participant's activity naming an overdue case commits no termination, and a case-scoped trigger ends the overdue embargo before it acts.

## Pros and Cons of the Options

### Compose every received delivery into one tree

- Good, because it states ADR-0022's chosen option for every handler, not only for the commit.
- Good, because the new stage is named and limited, so it cannot become a way to commit the activity's own effects early.
- Bad, because it is a multi-PR migration.

### Amend the one-tree rule with named exceptions for the expiry trees

- Good, because it changes no code.
- Bad, because it legalizes the Python-chosen cascade ADR-0022 rejected.
- Bad, because the door-check, refusal, alternative-branch and follow-up trees remain in breach, and each new clock-driven step would ask for another exception.

### Keep four stages and write the expiry as a refusal effect

- Good, because the stage model is unchanged.
- Bad, because an expiry whose prompting activity is admitted is never written, so a new Offer after the old one expired leaves the ledger showing two open Offers (CM-21-014).

## More Information

- [ADR-0022](0022-single-bt-execution-for-received-side-case-actor-routing.md) set the one-tree contract this record extends to helpers.
- [ADR-0111](0111-intake-is-the-first-received-side-stage.md) set the four stages; this record adds the clock-decision stage between its door guards and precondition guards.

Generated spec requirements: `case-ledger-processing.yaml` CLP-10-005, CLP-10-006 and CLP-10-010 (amended), CLP-10-025; `sync-ledger-replication.yaml` SYNC-14-009; `behavior-tree-integration.yaml` BT-15-003.

Source: ISSUE-4585.

Revision 2 (2026-10-15), from the maintainer's decisions on ISSUE-4641: detail 4 counts a clock decision's entries by the AS2 activities it needs instead of limiting it to one entry, and detail 5 makes the embargo end-time check a clock decision of every case tree with both door guards, with the scope note that a case-scoped trigger composes the same stage.

## Amendment — 2026-10-21

Detail 6 stands in its rule (a drained entry is its own delivery, under the receiving actor, never run inline or in a nested bridge run), but what is handed back is replaced.

Replaced text, in detail 6: "The buffer holds the entry, not the Announce that carried it, so the hand-back wraps it in an Announce attributed to the case's CASE_MANAGER."
In Consequences: "a handed-back entry comes from the CASE_MANAGER and runs the same inbox path as any delivery"; "Bad, because the hand-back needs a new driven port and an adapter for the actor's own inbox"; and "Neutral, because the gap buffer stays in memory, so a restart loses parked entries exactly as it does today."

Now: a participant holds the `Announce(CaseLedgerEntry)` it received, as the body that arrived, the way the inbox holds an activity deferred until its case is known (IO-03-004), never the entry alone (SYNC-14-001).
When a commit or a case seed makes that entry appliable, the drain replays the held `Announce` through the receiving actor's own inbox as a delivery of its own (SYNC-14-009).
Nothing is built and nothing is attributed to a sender who did not send it: the replay carries the first delivery's received evidence, and intake, which archived that delivery when it arrived, archives nothing new.
The driven port only queues a held activity for replay, and the holding area is kept in the receiver's store, so a restart no longer loses what is held.

The wrapped Announce was never sent by anyone, yet since received bodies became the archive (ADR-0149) intake recorded it as received evidence from the CASE_MANAGER.
In the maintainer's words: "If you didn't receive the Announce, you didn't receive the Announce, you can't just make one up."
Decided by Allen D. Householder, 2026-10-21 (ISSUE-5012, Epic #3738).
