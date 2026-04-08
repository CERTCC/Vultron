# Protocol Event Cascades

## Overview

The Vultron Protocol is designed to be event-driven with clear causal
relationships between primary events and their consequences. When a
primary event occurs (e.g., submitting a report, validating a report,
accepting an invitation), cascading effects SHOULD be automated rather
than requiring separate manual triggers.

This design principle is fundamental to demonstrating protocol
correctness: demos and real deployments alike should show that the
protocol drives the right behaviors automatically from minimal primary
inputs.

## Design Principle

**Automate cascading consequences via behavior trees wherever possible.**

The demo-runner (or a human operator, or an agentic client) should only
need to trigger *primary events*. Everything else should be a
consequence of those events, cascading through the system via the
defined behaviors of the actors according to the protocol.

**Primary events** (actor-initiated, require explicit trigger):

- submit-report (finder creates and offers a report)
- validate-report (vendor validates a received report)
- add-note (any participant adds a note to a case)
- propose-embargo (coordinator proposes embargo terms)
- terminate-embargo (actor announces embargo end)

**Cascading consequences** (should be automated):

- submit-report → case creation → participant setup → embargo
  initialization → notification to finder (`Create(Case)`)
- validate-report → validation logic only (case already exists)
- accept-invitation → engagement (RM→ACCEPTED)
- add-note-to-case → broadcast note to all case participants
- case state change → broadcast update to all participants (CM-06-001)

## Identified Gaps

The following cascades are not yet fully automated. Each gap has a
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

## Relationship to Demo Correctness

The purpose of the D5 demos is to demonstrate that the protocol
*actually works*, not merely to exercise the API. When a demo-runner
manually triggers intermediate steps that should be automated
consequences of primary events, the demo is misleading — it shows
puppeteered behavior rather than genuine protocol-driven automation.

Every manual trigger in a demo that should be a cascade represents
either:

- A gap in BT automation that needs to be filled
- A missing outbox delivery path that needs to be connected
- A missing `to` field on an outgoing activity

These gaps should be systematically identified and resolved before
demo sign-off (D5-7).

## Related

- `specs/case-management.md` CM-06 (case update broadcast), CM-11
  (invitation acceptance lifecycle)
- `specs/behavior-tree-integration.md` BT-06, BT-10
- `specs/triggerable-behaviors.md` TRIG-07-001
- `notes/activitystreams-semantics.md` (state-change notification model)
- `notes/bt-integration.md` (BT design decisions)
