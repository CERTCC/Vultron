# Protocol Event Cascade Gaps (Archived)

**Archived from**: `notes/protocol-event-cascades.md`
**Reason**: All identified gaps (D5-6-AUTOENG, D5-6-NOTECAST, D5-6-EMBARGORCP,
D5-6-CASEPROP) and the specific D5-7-BTFIX anti-pattern violations are
fully resolved as of PRIORITY-310, PRIORITY-320, and PRIORITY-330.

---

## Identified Gaps (Resolved)

The following cascades were not yet fully automated. Each gap had a
corresponding implementation task in `plan/IMPLEMENTATION_PLAN.md`
under PRIORITY-310.

### Invitation acceptance does not trigger engagement (D5-6-AUTOENG)

When an actor accepts an invitation to a case
(`AcceptInviteActorToCaseReceivedUseCase`), the current implementation
pre-seeds RM states to RECEIVED→VALID but does NOT automatically
advance to ACCEPTED. A separate `engage-case` trigger is required.

The protocol docs describe acceptance of an invitation as implying
engagement. The use case should invoke `SvcEngageCaseUseCase` internally
after creating the participant, which would advance RM to ACCEPTED and
emit the appropriate notification activity.

**Design Decision**: Acceptance of an invitation MUST automatically
advance the accepting actor's RM state to ACCEPTED (see CM-11-001).

### Note broadcast to case participants (D5-6-NOTECAST)

`AddNoteToCaseReceivedUseCase` stores the note in the case but does not
broadcast it to other participants. In the two-actor demo, notes are
manually forwarded via direct HTTP POST. The case owner (CaseActor)
should broadcast new notes to all participants via the outbox after
processing an `AddNoteToCase` activity.

Recipients should be derived from `case.actor_participant_index`,
excluding the note's author.

### Embargo Announce activity addressing (D5-6-EMBARGORCP)

> **Note**: Per ADR-0015, `InitializeDefaultEmbargoNode` moves to the
> `receive_report_case_tree` BT (invoked by `SubmitReportReceivedUseCase`),
> where it runs *after* participant nodes. Participants now exist at
> embargo initialization time, so the `to` field CAN be populated.

The `InitializeDefaultEmbargoNode` creates an `Announce(embargo)`
activity that is queued to the outbox with no `to` field. In the current
(pre-ADR-0015) validate-report BT, this node runs before participant nodes,
so there are no recipients to address even if the field were populated.

Under ADR-0015, this ordering problem is resolved: the case-from-report BT
creates participants before initializing the embargo, so recipient
addresses are available. However, if the separate `Announce(embargo)` is
still redundant given that the finder learns about the embargo from the
embedded case object in the `Create(Case)` activity, the standalone
Announce MAY be removed in favour of the simpler `Create(Case)` information
path (Option 2 below).

Options:

1. Populate the `to` field on `Announce(embargo)` from the participant
   index now that participants exist at embargo creation time (enabled
   by ADR-0015 reordering).
2. Remove the standalone Announce and rely on the `Create(Case)` activity
   to carry embargo information via `VulnerabilityCase.active_embargo`.

Option 2 is recommended as simpler: the finder already learns about
the embargo from the embedded case object in the `Create(Case)`
activity. The standalone Announce is redundant given this information
path.

### Case propagation for multi-actor flows (D5-6-CASEPROP)

Two related issues affect multi-actor case propagation:

1. `EmitCreateCaseActivity` (in `create_case` BT) creates a
   `VultronCreateCaseActivity` with no `to` field, so receiving actors
   cannot re-broadcast the case to other participants.

2. In the three-actor demo, `actor_engages_case()` calls the
   `engage-case` trigger on the case-actor container instead of the
   actor's own container. Protocol-correct behavior requires the actor
   to call `engage-case` on their own container, which queues an
   `RmEngageCaseActivity` to their outbox for delivery to the
   case-actor's inbox. This requires the actor to have a local copy of
   the case in their own DataLayer (received via `Create(Case)`
   delivery).

Both issues are symptoms of incomplete case propagation infrastructure.

---

## Anti-Pattern (the resolved D5-7-BTFIX violations)

```python
# ❌ ANTI-PATTERN — cascade outside the tree (now fixed)
class ValidateCaseUseCase:
    def _auto_engage(self, ...):
        SvcEngageCaseUseCase(self._dl, event).execute()  # NOT in tree

    def execute(self) -> None:
        bridge.execute_with_setup(self._dl, bt, bb)
        self._auto_engage(...)  # ← called AFTER BT, invisible in tree
```

The validate→engage cascade was fixed by implementing it as a child subtree
of the validate BT, mirroring the canonical `?_RMValidateBt → ?_RMPrioritizeBt`
structure. See `notes/canonical-bt-reference.md`.
