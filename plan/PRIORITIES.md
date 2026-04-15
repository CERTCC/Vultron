# Priorities

## Important note about priority numbers

Priority numbers are ascending, so lower numbers are higher priority.
The scale is not linear, it's just intended to provide a rough ordering and
allow for space between to add new priorities in the future if needed. The
priority numbers themselves do not have any inherent meaning beyond their
relative order.

## Priority 90: Fully address ADR-0013 and OPP-06

`docs/adr/0013-unify-rm-state-tracking.md` was created to capture the decision to unify state
tracking for the RM lifecycle. As noted in `notes/state-machine-findings.md`,
there are a number of steps to be taken to fully implement this
decision. We need to clearly identify and execute those steps before we
proceed with the next priority. These need to be added to `notes/`, `specs/`,
and `plan/IMPLEMENTATION_PLAN.md` tasks as appropriate.

We should also capture references to OPP-06
in the relevant `notes/` files, and in `specs/` and in the implementation
plan.

This priority covers both *capturing* the tasks, requirements, and notes,
and *implementing* the changes needed to fully realize this aspect of the
design.

## Priority 100: Actor independence

Each actor exists in its own behavior tree domain. So Actor A and Actor B
cannot see each other's Behavior Tree blackboard at all. They can only interact
through the Vultron Protocol through passing ActivityStreams messages with
defined semantics. This allows us to have a clean model of individual
actors making independent decisions based on their own internal state.

Implementation Phase OUTBOX-1 logically falls under this priority, because
it's part of getting messages flowing between actors. But it does not
fully achieve this goal by itself.

## Priority 200: Case Actor as source of truth for case state

The CaseActor becomes a resource that can manages the VulnerabilityCase. While
each Actor may maintain a copy of the case within their own system, the CaseActor
is the source of truth for the case state. It can update the case based on
inputs from other actors, and other actors can query the CaseActor for the
current state of the case when needed. The CaseActor is also responsible for
enforcing any rules or constraints on the case state, and for coordinating
actions between actors based on the case state. It can act as a broadcast
hub for case updates, sending notifications (as direct messages) to other actors
(listed as CaseParticipants) in the case.

The CaseActor must be instantiated at the beginning of the case lifecycle and
must exist until the case is closed. Each CaseActor handles exactly one VulnerabilityCase,
the one it was instantiated for. The CaseActor knows who the case owner (another Actor, NOT the CaseActor) is because
it is stored in the VulnerabilityCase itself. The CaseActor must restrict certain
activities to the case owner, such as closing the case or transferring ownership.
These details are defined in the `vultron_as:CaseOwnerActivity`
in `ontology/vultron_activitystreams.ttl`.

## Priority 250: pre-300 cleanup

Items to complete before we get to D5-2 and the other priority 300 tasks.
This includes: SPEC-AUDIT-1, SPEC-AUDIT-2, SPEC-AUDIT-3,
NAMING-1, QUALITY-1, SECOPS-1, DOCMAINT-1, REORG-1, and SM-GUARD-1.

## Priority 300: Multi-Actor Demo Scenarios

Extended multi-actor demo scenarios are documented in
`notes/demo-future-ideas.md`. These demos — Two-Actor (Finder + Vendor),
Three-Actor (Finder + Vendor + Coordinator), and MultiParty (with ownership
transfer and expanded participants) — are important for showcasing the
capabilities of the Vultron Protocol and demonstrating how components work
together. Implementing these demos will help identify gaps in the current
implementation and provide a basis for further development and refinement.
Each scenario requires actors running in independent containers communicating
via the Vultron Protocol, with CaseActor managing case state.

See `notes/demo-future-ideas.md` for the full scenario descriptions.

Specific tasks include (but not limited to): D5-1, D5-2, D5-3, D5-4, D5-5.

## Priority 310: Address feedback on demos

This is a placeholder priority for addressing feedback on the multi-actor
demo scenarios and their implementation. We should not proceed with
priorities beyond this until we have completed all known feedback.

All D5-6 tasks belong here.

IDEA-260408-01-1 through IDEA-260408-01-7 are all related to addressing  
feedback on the demos, so they also belong here.

EMBARGO-DUR-1 — update EmbargoPolicy model to ISO‑8601 durations (pending)

## Priority 320: additional demo feedback

Tasks in this priority: D5-7-EMSTATE-1, D5-7-AUTOENG-2,
D5-7-TRIGNOTIFY-1, D5-7-DEMONOTECLEAN-1.

These are the remaining round-2 demo feedback tasks that are independent of
the SYNC replication work.

Two tasks originally in this group — D5-7-CASEREPL-1 and D5-7-ADDOBJ-1 —
have been **superseded by SYNC-2** (Priority 330). The `Announce(CaseLogEntry)`
replication path replaces the direct `Create(VulnerabilityCase)` and
`Add(CaseParticipant)` delivery paths to participant actors. Implementing
stopgap fixes would require rework immediately after SYNC-2.

D5-7-DEMOREPLCHECK-1 is **deferred to after SYNC-2** (Priority 330) because
meaningful finder-replica verification requires checking log-state consistency,
not just field equality.

**D5-7-TRIGNOTIFY-1** (populate `to` field in trigger activities) is also a
prerequisite for SYNC-2 fan-out to work correctly; complete it as part of
Priority 320 before starting Priority 330.

## Priority 325: TinyDB → SQLModel/SQLite Datalayer Migration

Replace the TinyDB persistence backend with a SQLModel/SQLite adapter.
TinyDB's O(n) I/O cost (whole-file rewrite on every operation) was measured
concretely in BUG-2026041001: the test suite grew from ~13 s to 15+ minutes
as test coverage expanded. The fix required a `pytest_configure` monkey-patch
to force `MemoryStorage` globally — accidental complexity paid entirely to
work around a TinyDB limitation, not to test any application behavior.

**Approach**: Single-table polymorphic SQLModel storage model
(`VultronObjectRecord`) defined entirely in the adapter layer. Domain models
(Pydantic) are unchanged. SQLModel is isolated to the adapter.
Test isolation via `sqlite:///:memory:` replaces the monkey-patch.

Tasks: DL-SQLITE-ADR, DL-SQLITE-1, DL-SQLITE-2, DL-SQLITE-3, DL-SQLITE-4,
DL-SQLITE-5. All must complete before D5-7-HUMAN (Priority 330).

IDEA-26040901 (TinyDB table consolidation) is superseded by this migration.
IDEA-26040902 is the primary driver.

## Priority 330: SYNC implementation + demo sign-off

This priority covers the log-centric replication work (formerly Priority 400)
and the final demo quality gate. It is elevated above the old Priority 400
because D5-7-HUMAN sign-off cannot happen until demos work correctly with
log-sync in place.

**OUTBOX-MON-1** (background outbox drain loop) is a hard prerequisite for
SYNC: without it, SYNC-2 replication requires manual triggers. Complete it
before SYNC-1.

Sequential dependency chain:

1. OUTBOX-MON-1 — automated outbox delivery (prereq for SYNC-1/SYNC-2)
2. SYNC-1 — local append-only case event log (prereq: OUTBOX-MON-1)
3. SYNC-2 — one-way log replication via `Announce(CaseLogEntry)` (prereqs:
   SYNC-1, OUTBOX-MON-1, D5-7-TRIGNOTIFY-1 from Priority 320)
   - **Subsumes D5-7-CASEREPL-1**: finder receives case state via
     `Announce(CaseLogEntry)`, not `Create(VulnerabilityCase)`
   - **Subsumes D5-7-ADDOBJ-1**: inline-objects principle applied to
     `Announce` delivery; direct `Add/Create` delivery to participants
     is retired
4. SYNC-3 — full sync loop with retry/backoff (prereq: SYNC-2)
5. D5-7-DEMOREPLCHECK-1 — finder replica verification via log state
   (prereq: SYNC-2)
6. D5-7-HUMAN — single project-owner sign-off on demo completeness
   (prereqs: SYNC-2, D5-7-DEMOREPLCHECK-1, all other D5-7 tasks)

See `notes/sync-log-replication.md` and `notes/case-log-authority.md` for
the architectural rationale.

## PRIORITY 340: Wire translation

All WIRE-TRANS tasks fall here.

## Priority 350: Update python version and other maintenance tasks

**D5-7-HUMAN** (project-owner sign-off on demo completeness) is the gate to
enter Priority 350 and beyond.

General housekeeping items. Non-blocking; can proceed in parallel with or
after Priority 330.

CONFIG-1, TOOLS-1, DOCS-3, VOCAB-REG-1.1, VOCAB-REG-1.2

## Priority 400: Initial SYNC implementation

> **Superseded by Priority 330.** The SYNC work has been elevated to
> Priority 330 because D5-7-HUMAN sign-off depends on SYNC-2 completing
> the demo replication story. OUTBOX-MON-1 was also moved from Priority
> 350 to Priority 330 as a hard SYNC prerequisite. See Priority 330 for
> the full task list and sequencing.

## Priority 500: Re-implement "fuzzer" nodes from the original simulator

As we originally built out the `py_trees` implementation, we replaced
certain fuzzer nodes from the simulator (`vultron/bt`) with deterministic nodes
that simply
return success. While this initially allowed us to focus on the core
behavior tree logic, it also means that we are not able to demonstrate the
full range of behaviors that the Vultron Protocol is designed to support.
Re-implementing these nodes with more realistic behavior will be important for showcasing the
capabilities of the system and for moving towards a production-ready implementation.
The "fuzzer" implementation in the simulator worked well enough, so there is
not much need to change the overall design, but we will need to reimplement
it in the new codebase using `py_trees` as the foundation. The underlying
`vultron/bt/base/fuzzer.py` module (and all the other `fuzzer.py` modules in
`vultron/bt/`) can be used as a structural reference for the new implementation.

## Priority 1000: Agentic AI readiness

We are going to want to allow for the possibility of agentic AI integration
into the vultron coordination process in the future. How this will happen is
still an open question. One possibility we can imagine coordination agents
that behave as ActivityPub Actors and participate in cases as CaseParticipants alongside
humans.

A more likely scenario is that we want to support agentic AI agents
interacting with cases as well on the
backend (i.e., not as ActivityPub Actors, but as API or command
line clients.) We may have local agents that interact directly with
the behavior trees or other internal system components via MCP. This would
be an adapter that parallels the API and CLI adapters in the hexagonal
architecture. These agents would not be ActivityPub Actors and would not
directly participate in cases, but would instead be more like assistants to human participants
who are directing them to perform specific tasks.

`AR-09-001` through `AR-09-004` and similar tasks will fall here.

We will need to design the system in a way that allows for either of these
possibilities to be implemented in the future without requiring major refactoring.

## Priority 2000: Upgrade former "fuzzer" nodes to full implementations

See `notes/bt-fuzzer-nodes.md` for details on a set of fuzzer nodes that
were implemented as placeholders in the original simulator, but that
represent external touchpoints for the real process. Some of these nodes can
be fully automated, others will require outside judgment, human input, or
manual work. They might rely on external tools or services that we will need
to integrate with. Implementing these nodes will be important for moving
from a prototype to a production-ready system, but they also represent a
number of decisions and implementation work that is not core to being able
to demonstrate the core behavior tree and coordination logic.

## Priority 3000: Miscellaneous tasks

BT-2.2, BT-2.3

## Priority 50000: Full RAFT consensus implementation

SYNC-4 enables RAFT consensus for the CaseActor process. Before we get here
we will need to establish how we want to handle the CaseActor scaling and
failover process.

## Priority 99999: Remaining Requirements and Documentation Updates

The project is currently in prototype development mode, therefore requirements
that are marked as `PROD_ONLY` are temporarily a lower priority than other
requirements. See `specs/prototype-shortcuts.md` for the prototype-stage
deferral policy.

USE-CASE-01
USE-CASE-02
EP-02
EP-03
AR-04
AR-05
AR-06
AGENTIC-00
FUZZ-00
