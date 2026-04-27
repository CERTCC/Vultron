# Priority History

This file contains an append-only history of completed priority task groups.

---

## Priority 90: Fully address ADR-0013 and OPP-06

`docs/adr/0013-unify-rm-state-tracking.md` was created to capture the decision to unify state
tracking for the RM lifecycle. As noted in `archived_notes/state-machine-findings.md`,
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

INLINE-OBJ tasks also belong here.

## PRIORITY 340: Wire translation

All WIRE-TRANS tasks fall here.

## Priority 345: DataLayer auto-rehydration

DL-REHYDRATE: auto-rehydration in SQLite/TinyDB adapters so `dl.read()` and
`dl.list()` always return fully typed domain objects. Audit and remove manual
`model_validate` coercion in use cases after completion.

## Priority 347: Demo puppeteering, trigger completeness, BT node generalization

Addresses BUG-26041701 (bare-string `object_` in `CreateFinderParticipantNode`)
and IDEA-26041702 (generalize to `CreateCaseParticipantNode`). Also converts
scenario demos from spoofing to trigger-based puppeteering, adds missing trigger
endpoints, renames `evaluate-embargo` → `accept-embargo`, and reorganizes
`vultron/demo/` into `exchange/` (protocol fragments) and `scenario/`
(end-to-end workflows).

Tasks: P347-BUGFIX, P347-NODEGENERAL, P347-BRIDGE, P347-SUGGESTBT,
P347-TRIGGERS, P347-EMBARGOTRIGGERS, P347-DEMOORG, P347-PUPPETEER,
P347-SPECS.

Prereqs: P-345 (DL-REHYDRATE) must complete first.
Blocks: D5-7-HUMAN sign-off (gate to P-350).

## Priority 348: More Demo prep

DR-* tasks go here

## Priority 350: Update python version and other maintenance tasks

**D5-7-HUMAN** (project-owner sign-off on demo completeness) is the gate to
enter Priority 350 and beyond.

General housekeeping items. Non-blocking; can proceed in parallel with or
after Priority 330.

CONFIG-1, TOOLS-1, DOCS-3, VOCAB-REG-1.1, VOCAB-REG-1.2

## Priority 360: BT composability audit (IDEA-26041703)

Addresses the deeper concern from IDEA-26041703: BT nodes and subtrees should
be composable, reusable branches rather than one-off behaviors hard-coded to
specific actors or demo scenarios. The "fractal" composition pattern in
`vultron/bt/` is the intended model.

Deliverables:

- `notes/bt-reusability.md` — durable design note capturing the fractal
  composability pattern, the "trunkless branch" intent, and anti-patterns
  to avoid.
- `specs/behavior-tree-node-design.yaml` — formal requirements for BT node
  parameterization, composability, and reuse (e.g., nodes MUST NOT hard-code
  actor roles; roles/identities MUST be constructor parameters; reusable
  subtrees MUST be composed rather than duplicated).
- Codebase audit: identify one-off BT nodes or near-duplicate subtrees that
  should be refactored to use the composability pattern; produce a task list.

Can begin in parallel with P-347.

## Priority 400: Initial SYNC implementation

> **Superseded by Priority 330.** The SYNC work has been elevated to
> Priority 330 because D5-7-HUMAN sign-off depends on SYNC-2 completing
> the demo replication story. OUTBOX-MON-1 was also moved from Priority
> 350 to Priority 330 as a hard SYNC prerequisite. See Priority 330 for
> the full task list and sequencing.
