# AGENTS.md — `vultron/core/behaviors/embargo/`

Agent guidance for embargo-related BT nodes and subtrees in this package.

> For project-wide BT conventions see
> [`vultron/core/behaviors/AGENTS.md`](../AGENTS.md).

---

## Embargo Subtree Idempotency with Blackboard Flag

(ISSUE-750, 2026-06-08)

When a god node is decomposed into a sequence of leaf nodes, the original
single-pass semantics may break if duplicate-run behavior depended on the
god node's internal guard. Preserve idempotency explicitly:

- Add a blackboard flag (e.g., `embargo_initialized: bool`) that is set
  to `True` only when the current execution actually created a new embargo.
- Side-effect leaves that should only fire on first initialization (e.g.,
  seeding participants, creating events) MUST check this flag before
  acting.
- When moving EM transition logic to `EmbargoLifecycle.propose_embargo`,
  keep event creation and participant-seeding behavior aligned with
  existing duplicate-report tests to avoid introducing regressions.

---

## Routing-Gated State Mutation

(BT-19, 2026-06-26; see `specs/behavior-tree-integration.yaml` BT-19-001,
BT-19-002)

A BT Sequence that performs a protocol state-machine transition (EM, RM, or CS)
and then routes an outbound activity MUST resolve all routing prerequisites
in a read-only guard node placed **before** the state-mutation node.

**Why ordering matters**: Once the DataLayer accepts a state write (e.g.,
`EM=EXITED`), the transition is committed. If the subsequent routing step
then fails (missing Case Manager, missing factory), the outbound notification is
never sent. Peers retain the prior state; local state has advanced — a
divergence window that requires ledger-sync catch-up (SYNC-10) to repair.
Moving the routing guard to the top of the Sequence eliminates the divergence:
if routing prerequisites are absent, the tree returns `FAILURE` with zero
DataLayer state change.

**Shared factory requirement**: Duplicated monolithic BT nodes that inline both
state mutation and dispatch in a single `update()` method drift independently.
The canonical factory-composed path may correctly order the guard, while the
automatic-cascade monolith retains the old unsafe ordering, reintroducing the
divergence bug on that path only. All call sites for the same lifecycle
transition MUST use a shared BT factory function (BT-19-002).

**Canonical Sequence structure**:

```text
Sequence
├── ResolveCaseManagerNode          ← read-only guard; FAILURE = bail, no write
├── <StateTransitionNode>           ← mutation committed after guard passes
└── <SendDispatchNode>              ← routing succeeds because guard already verified
```

**Anti-pattern** (Issue #1054 — `TerminateEmbargoNode`):

```text
Sequence
├── TerminateEmbargoLifecycleNode   ← mutation committed first ← ❌
└── SenderSideBT                    ← routing checked second; fail = divergence
```

**Fix**: Extract a shared factory (`terminate_embargo_bt`) that places
`ResolveCaseManagerNode` before the termination write (now
`CommitAndApplyEmbargoTerminationNode`), and replace
all standalone monolithic nodes with the factory output. Both trigger and
cascade call sites use the shared factory directly (BT-19-002, PR #1263).

---

## Embargo Writes Run Only in the CASE_MANAGER Arm

(EP-09-008, #3962, #4085, #4112)

Every embargo trigger tree in `trigger_tree.py` ends in `_by_role()`'s two
mutually exclusive arms. Add a new embargo write to the **CASE_MANAGER arm**
only, and build it on the copy model (§ "Converting an Arm to the Copy
Model" below): decide, commit, then apply, then `EmitCaseStatusUpdateNode`.
For a lifecycle node that is `*EmbargoLifecycleNode(...).deciding()`
(`STRICT`, on a staged store) → `CommitEmbargoDecisionNode(decision_from=result_out)`
(`nodes/manager_commit.py`; a decision it sends is queued before it is
committed, SYNC-09-002, and applied only after its entries commit). The
other arm writes no EM state:
it queues to the manager through `sender_side_bt` with `_asserting()`, which
writes `result_out[ASSERTED_ACTIVITY_KEY]` for the pending-assertion record.
The one exception is `reject_proposed_embargo_bt` (the P/X/A abandonment):
its other arm sends nothing at all (EMB-16-002), so it passes
`otherwise_suffix` and is not named `...AskCaseManager`.

- A decision every replica learns from the entry (`Accept`/`Reject`) is
  addressed to nobody; a teardown goes to every *other* participant
  (`notify_participants=True`). Never address the manager's own outbox to
  itself — that is #4112.
- The termination arm is converted to the copy model (#4714):
  `CommitAndApplyEmbargoTerminationNode` decides, commits the `Remove`, then
  applies it. With no use case to build the activity (the cascades and the
  lazy end-time check) it calls the factory itself.
- The activation arm is converted too (#4716):
  `CommitAndApplyEmbargoActivationNode` (`nodes/activation_commit.py`) runs
  `EmbargoLifecycle.decide_activation()`, commits the `Accept` (the whole
  `ACTIVATE` step and the owner's own `AGREED` row), then one
  `Update(EmbargoConsent)` per `CARRY_OVER` row, then applies. It does not use
  `_answer_arms()`; the received owner-decision tree runs the same node with
  no builder, after `ActivationAppliesNode` trial-applies among the guards.
- Ratchet: `test/architecture/test_embargo_trigger_writes_are_case_manager_gated.py`
  fails on any EM write node (`_EM_WRITES`: an `_EmbargoLifecycleNode` or a
  copy-model commit-and-apply node) outside the gate, and on a new public
  factory that is not listed.
- A test of the manager arm runs in the manager's own store; a test of the
  ask arm needs a replica store whose `actor_id` is the asking participant
  (BT-05-005).

## Converting an Arm to the Copy Model (ADR-0124, #4713)

The propose and answer arms (`_propose_arms`, `_answer_arms`), the received
proposal, relay and answer effects, the manager's policy consent and the stub
re-issue (#4715), termination (#4714), the received withdrawal (#4717),
activation on the received path and expiry (#4716), and the owner's-rejection
replica slot (#4784) are converted. A
converted CASE_MANAGER arm decides first (guards, `EmbargoLifecycle` checks,
policy), then hands the result to `commit_and_apply_embargo_entries()`
(`copy_commit.py`) as `PlannedEmbargoEntry` values in commit order:

1. The act's own entry, whose `change` is the `RegisterStep` the activity
   carries (`ACTIVATE` includes the supersede, `TERMINATE` the cancels), or,
   for a participant's `Accept`/`Reject(Invite(EmbargoEvent))`, the row the
   answer states (`ConsentRowChange.answer()`: that entry is the row's entry,
   and no second one records it, ADR-0122), and
   whose `commit` queues and commits the act; `commit=None` when the guarded
   commit already committed it (a received act, same transaction).
2. One `consent_row_entry()` per consent row the act changes.

For a received act, also run `trial_apply()` among the tree's guards, before
the guarded commit, so a refused step refuses the act. The helper
trial-applies every planned entry through `apply_embargo_change()` before
committing any, so a refused trial (`VultronEntryRefusedError`) commits
nothing. The trial, every commit and the case-file save run in one
`CasePersistence.transaction()`, so a failed commit writes nothing either
(CLP-07-015, ADR-0146); do not add a repair pass for a half-done act. Several
acts that must land together go through one call, as one entry list. A later
node that commits a consequence of the act (`ReissueStubInvitesNode`, a
`RelayEmbargoInviteToEachNode`) must run with the act's commit node in one
`ActTransaction` (`core/behaviors/act_transaction.py`): pass `as_one_act=True`
to `create_case_manager_gated_tree` (every `_by_role` arm does) or
`as_one_act=True` to `create_receive_activity_tree`, which adds the
received act's own commit (ADR-0151).
Call it from a node's `update()`, never from `execute()`. The replica slot
for the same entry subclasses `ApplyEmbargoChangeFromLedgerNode`
(`sync/nodes/embargo_copy_effect.py`) and only names the change (`_change()`).
Never call `EmbargoLifecycle`, `apply_pec_transition` or `write_uninvited_rows`
from a replica slot.

Where the decision is an existing `EmbargoLifecycle` operation, do not
re-derive its row changes by hand: run it on a staged store and let
`decided_entries.py` turn what it would have written into the entries. A
lifecycle node takes `.deciding()` (the arm's `CommitEmbargoDecisionNode`,
given `decision_from=result_out`, commits the act first) or
`.applying_after(cause_id)` (a received act's guarded commit ran first);
other nodes call `decide_commit_and_apply()`. A received answer's entry is
committed before its effects, so its tree runs the same decision among its
guards (`EmbargoAnswerAppliesNode`, `nodes/answer_record.py`) and refuses an
answer that would record nothing the case can take. A received withdrawal
does the same (`EmbargoWithdrawalAppliesNode`); both guards subclass
`EmbargoDecisionAppliesNode`, gated by `case_manager_decision_guard()`, and
both effects subclass `_RecordReceivedConsentNode` (`nodes/proposal.py`),
which commits each further row with the received act as its cause. A new
received consent act reuses those two frames. An act whose entry carries no
change of its own (the `Leave`) has a replica slot that stores the embargo
and writes nothing, as the Invite and re-invite slots do; its rows are
copied by the consent slot. The decision check raises
`VultronBTInternalError` when the operation wrote anything its entries do not
carry. A consent-row `Update`'s id derives from its cause and the row, so the
cause must be the act itself (the relayed Invite, the re-issued stub), never
an id two acts share.

A decision the CASE_MANAGER takes from the clock or policy about one row (an
RSVP time-out, honouring a late Accept) is the occasion for one act, its
factory-built `Update(EmbargoConsent)` carrying the row, committed before the
row is written (`nodes/expiry_commit.py`, ADR-0140). No second entry records
the decision, and none is attributed to the invitee; the consent slot copies
the row. A row the actor's own activity states (the owner's
agreement at activation, a joiner's at its stub Accept) is applied from that
activity's entry on both sides, decided by the same function
(`models/embargo_consent_move.py`: `owner_agreement`, `joiner_agreement`).

`terminate_embargo_bt` is the worked example (#4714):
`decide_termination()` (`services/embargo_lifecycle/activation.py`) names
the `TERMINATE` step, `CommitAndApplyEmbargoTerminationNode`
(`nodes/termination_commit.py`) commits the `Remove` that carries it, then
applies it. The `Remove` entry is the whole step, cancels included, and
writes no consent row. The replica slot is `ApplyEmbargoTeardownNode`
(`nodes/teardown.py`), which ends the embargo the `Remove` names.
