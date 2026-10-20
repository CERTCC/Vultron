---
source: CONCERN-4789
timestamp: '2026-10-16T20:20:50.782845+00:00'
title: The CASE_MANAGER commits the owner's Reject even when it answers it with ET,
  so replicas must infer the skip
type: learning
---

## Concern

The #4713 decision: one ledger entry records one AS2 activity/object pair, and the act's own activity carries its whole register step. The owner's `Reject(EmbargoEvent, target=Case)` entry is therefore the `REJECT` step. A replica copies that step and decides nothing (ADR-0124, CM-23-016).

There is one case where the CASE_MANAGER commits that `Reject` entry but does not perform its step. The owner rejects the last open revision while CS is public, exploited or attacked. The CASE_MANAGER then answers with ET instead of returning to the prior terms (EMB-04-002, MSM-07-009). The `Remove(EmbargoEvent, target=Case)` entry that follows carries the `TERMINATE` step, which cancels the revision (EP-08-004). The received tree is `_decide_owner_rejection` in `vultron/core/behaviors/embargo/owner_decision_tree.py`.

So a replica can't just copy `REJECT`. If it did, it would end with the revision `REJECTED`, while the CASE_MANAGER holds it `CANCELLED` (the convergence #4364 pins).

## Current state: merged as a tracked deviation (PR #4810, #4784)

The maintainer chose to merge now and fix here, as with #4618/#4641.

- The replica slot `ApplyEmbargoProposalRejectionFromLedgerNode` (`vultron/core/behaviors/embargo/nodes/activation_effect.py`) overrides the copy frame's skip hook `_left_to_a_later_entry` (`vultron/core/behaviors/sync/nodes/embargo_copy_effect.py`). It evaluates the shared predicate `rejection_ends_embargo` on its own case file and skips the entry. It also skips a seeded replica that is already past the termination.
- The skip reads only the case (no clock, id, policy or outside state), so replicas at the same ledger position still match. It is still lifecycle logic on replay, which CM-23-016 forbids. The code docstrings, `notes/embargo-lifecycle.md`, `notes/case-communication-model.md`, the EP-09-007 note and the PR body name it as a deviation tracked here.
- `test/architecture/test_embargo_replica_slots_copy.py::test_only_the_owner_rejection_slot_decides_a_skip` fences it: no other slot may override the skip hook.

**Keeping this as a sanctioned exception is not the target.** The interim exists only until one of the options below is chosen.

## Why it matters

- A future change to the EMB-04-002 condition must change the predicate on both the CASE_MANAGER and the replica together, or replicas diverge.
- The ledger records a `Reject` whose register step never happened, so the entry alone doesn't tell an auditor what the step was.

## Options (maintainer decision needed)

1. **Refuse the owner's `Reject` before commit in that case, and terminate as the CASE_MANAGER's own act.** This is how MSM-07-008 refuses an activation with P/X/A set. The ledger then holds only the CASE_MANAGER's `Remove`, and the owner is told its `Reject` was refused and the embargo terminated instead (refusal feedback through the factory, CLP-02-005).
   - Changes MSM-07-009 and what the owner is told.
   - Check it against CLP-02-012: is the participant's `Reject` a case event that must be ledgered even when refused?
2. **Let the committed entry state its own step.** The CASE_MANAGER commits the `Reject` with an explicit marker that it carries no register step (answered by ET), so the replica copies a no-op and decides nothing.
   - Changes the entry shape, which needs an ADR-0124 / ADR-0122 revision.
   - Keeps the owner's `Reject` in the ledger as admitted.

## Acceptance criteria (whichever option is chosen)

- [ ] AC-1: the replica slot for the owner's `Reject` copies only. `_left_to_a_later_entry` is no longer overridden there, and the architecture-test exception is removed (no slot overrides the skip hook).
- [ ] AC-2: after the ET-answered rejection, the CASE_MANAGER's and a replica's register and consent rows are equal, with the revision `CANCELLED` on both (#4364's convergence test still passes). A seeded replica past the termination still replays forward only.
- [ ] AC-3: the specs and ADRs touched by the chosen option (MSM-07-009, EMB-04-002, CM-23-016's notes, ADR-0124/ADR-0122) are edited in place to match. The "tracked deviation" wording in code, the notes and the EP-09-007 note is removed.

Related: #4784, #4810, #4713, #4364, #4641 (the earlier deviation handled the same way).

Where: vultron/core/behaviors/embargo/nodes/activation_effect.py; vultron/core/behaviors/sync/nodes/embargo_copy_effect.py; vultron/core/behaviors/embargo/owner_decision_tree.py

**Resolved**: 2026-10-16 — implementation tracked in #4850. Chosen fix (option 3, not in the original list): the owner's Reject always carries its REJECT step, and the CASE_MANAGER's ET Remove follows in the same decision; replicas copy both.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4848>.

Spec: `specs/message-semantics-mapping.yaml`.
