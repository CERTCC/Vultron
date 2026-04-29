# Design Insights and Implementation Notes

This directory captures **durable design insights** for the Vultron project.
Unlike `plan/BUILD_LEARNINGS.md` (which is ephemeral), files here are
committed to version control and MUST be kept up to date as the
implementation evolves.

Archived historical notes (fully superseded or completed task logs) are in
`archived_notes/` — see its README for what is there and why.

## How to navigate

Files are grouped by domain. Read the **Load when** line for each file to
decide what to pull for your task. In most cases you need only 1–3 files.

---

## Architecture and Design

**`architecture-ports-and-adapters.md`**
Authoritative spec for Vultron's hexagonal (Ports and Adapters) architecture:
layer model (core / wire / adapter), adapter categories (driving / driven /
connector), file layout, Rules 1–8, dispatch/emit terminology, and compliance
checklist. Includes a "Compliance Reference" appendix of currently-clean code
paths.
**Load when**: designing new components, adding adapters, reviewing layer
boundaries, or investigating an import-layering violation.

**`datalayer-design.md`**
DataLayer design decisions: auto-rehydration contract (`dl.read()` / `dl.list()`
must return fully typed domain objects), storage record evaluation, vocabulary
registry entanglement analysis, and SQLModel/SQLite adapter design
(`VultronObjectRecord` single-table polymorphic design, actor scoping via
`actor_id` column, `sqlite:///:memory:` test isolation). The authoritative
reference for the DL-REHYDRATE implementation task.
**Load when**: implementing or modifying the DataLayer adapter, debugging typed
object round-trips, evaluating a future backend swap, or working on
DL-REHYDRATE.

**`domain-model-separation.md`**
Analysis of the current coupling between wire format (ActivityStreams), domain
logic, and persistence in `VulnerabilityCase`. Documents the recommended
three-layer separation and migration path, DataLayer isolation options (now
superseded by Priority 325), and `FooActivity` vs `FooEvent` naming. Includes
post-P75-2 architectural findings.
**Load when**: refactoring `VulnerabilityCase` or related models, evaluating
DataLayer backends, or planning domain/wire layer decoupling.

**`activity-factories.md`**
Factory functions as the public construction API for outbound Vultron protocol
activities. Documents the `vultron/wire/as2/factories/` package design: module
layout, factory function signatures, `VultronActivityConstructionError`, and
migration path from direct subclass instantiation. See also
`specs/activity-factories.yaml` (TASK-AF).
**Load when**: implementing outbound activity construction, migrating call
sites away from direct `vocab/activities/` subclass instantiation, or
debugging `ValidationError` during activity construction.

**`outbox.md`**
Outbox addressing requirements: `to:` field enforcement, `VultronOutboxToFieldMissingError`
exception design, `cc`/`bto`/`bcc` warning policy, and implementation details
for `handle_outbox_item()`. Source: `specs/outbox.yaml` OX-08-001 through
OX-08-004.
**Load when**: implementing or modifying outbox delivery logic, adding a new
outbound activity type, or debugging missing-`to:` errors.

**`actor-knowledge-model.md`**
Design decisions and implementation guidance for the Actor Knowledge Model
(AKM): how actors track knowledge about other actors, case participants, and
embargo state. References `specs/actor-knowledge-model.yaml` (AKM-01 through
AKM-08).
**Load when**: implementing actor knowledge queries, designing inter-actor
trust or awareness logic, or working on AKM spec requirements.

**`configuration.md`**
Design decisions for YAML-backed Pydantic configuration loading in Vultron:
`ActorConfig` neutral model, `LocalActorConfig` composition, default embargo
policy injection, and configuration file resolution order.
**Load when**: implementing or modifying actor configuration loading,
designing config-driven BT node behavior, or working on CFG-07-* requirements.

**`use-case-behavior-trees.md`**
Conceptual layering from Driver → Dispatcher → Use Case → BT → Domain Model.
Covers proposed module layout, protocol activity-to-use-case mapping, the
standardized `UseCase` protocol, and `SEMANTICS_HANDLERS` migration to core.
**Load when**: adding a new message type end-to-end, restructuring the
dispatcher or use-case layer, or deciding whether a use case needs a BT.

**`vocabulary-registry.md`**
Design for `VOCAB-REG-1`: `__init_subclass__` auto-registration, flat dict
structure, `VocabNamespace` enum as metadata, `Literal type_` heuristic for
detecting abstract vs concrete classes, and migration path (1.1 / 1.2).
**Load when**: adding new ActivityStreams vocabulary types, modifying the
registry decorators, or diagnosing vocabulary type-resolution issues.

**`federation_ideas.md`**
Open design exploration: AS2 as vocabulary (not full ActivityPub), actor /
inbox / outbox model, case object ownership, relay pattern, journal vs delivery
log, mirror consistency, instance trust, peering handshake, connector plugins.
**Load when**: scoping multi-instance federation, designing actor peering, or
evaluating the relay/journal delivery architecture.

---

## Protocol Semantics and Behavior Trees

**`activitystreams-semantics.md`**
Canonical guidance for how ActivityStreams activities are used as
state-change notifications (not commands): inbound vs outbound semantics,
`Accept`/`Reject` `object_` field conventions (inline typed object required),
`rehydrate()` patterns, `CaseActor` as authoritative case author, and
vocabulary examples.
**Load when**: implementing any inbound or outbound message handler, debugging
semantic extraction, or writing new ActivityStreams vocabulary classes.

**`stub-objects.md`**
Design notes for the AS2 minimalist object pattern (stub/stub-object): using
minimal `{"id": "...", "type": "..."}` references to reduce wire verbosity,
address privacy concerns (avoid leaking content to intermediaries), and support
future redaction. Covers the redaction concept and its relationship to
full inline objects.
**Load when**: designing outbound message payloads, evaluating object verbosity
trade-offs, or scoping privacy/redaction features.

**`bt-integration.md`**
BT design decisions (when to use BTs vs procedural code), py_trees patterns,
simulation-to-prototype translation strategy, and anti-patterns to avoid.
Also contains the **Canonical CVD Protocol Behavior Tree Reference** (merged
from the former `canonical-bt-reference.md`): trunk-removed branches model
and subtree composition examples.
**Load when**: implementing or modifying any BT node or use-case handler that
uses py_trees, deciding whether a new use case needs a BT, or diagnosing BT
execution issues.

**`bt-reusability.md`**
Fractal composability pattern for BT nodes and subtrees: the "trunkless branch"
model, parameterization guidelines, anti-patterns (hard-coded actor roles,
demo-specific logic in nodes, one-off subtrees, duplicated logic), and a
composability checklist. Operationalizes `specs/behavior-tree-node-design.yaml`
(BTND-01 through BTND-04).
**Load when**: designing a new BT node or subtree, auditing existing nodes for
composability violations, or refactoring near-duplicate BT implementations.

**`bt-fuzzer-nodes.md`**
Structured catalog (~1,500 lines) of all fuzzer nodes in the legacy BT
simulation, organized by topic with automation potential ratings. A ToC at the
top indexes by domain section (Vulnerability Discovery, Embargo Management,
Report Validation, Publication, etc.).
**Load when**: researching external dependency touchpoints for the CVD process,
implementing real replacements for fuzzer nodes, or scoping integration work
with external data sources.

**`protocol-event-cascades.md`**
Design principle for cascading automation: primary events vs cascading
consequences, identified gaps in BT automation and activity addressing
(invitation acceptance, note broadcast, embargo announce, case propagation).
**Load when**: implementing handler business logic and unsure what downstream
BT or outbox effects should be triggered, or debugging a demo that requires
manual intermediate steps.

**`event-driven-control-flow.md`**
Conceptual actor model: actors as workers consuming from a message queue
(inbox), running behavior trees, and emitting to an outbound queue (outbox).
Explains the queue/worker mental model as a *reasoning tool* (not an
implementation requirement), the role of external decision nodes as cascade
stopping points, their lineage from BT simulation fuzzer nodes, and their
future potential as UI or LLM integration seams.
**Load when**: reasoning about why a demo or use case should or should not
manually trigger intermediate steps, designing the boundary between automated
cascades and external decision nodes, or evaluating where UI or LLM agent
integration fits in the protocol flow.

**`bt-composability.md`**
Vultron's fractal composability principle for behavior trees: concrete patterns
for composing behavioural subtrees, the "trunkless branch" model applied at
the composability layer, and guidance for building reusable BT building blocks.
Operationalises `specs/bt-composability.yaml` (BTC-01 through BTC-04).
**Load when**: designing composable BT subtrees, auditing BT compositions for
violations, or working on BTC spec requirements.

**`bt-design-patterns.md`**
Idiomatic BT construction patterns from Colledanchise & Ögren applied to the
Vultron simulation and prototype implementations: factory methods, node
naming, status semantics, and anti-patterns.
**Load when**: implementing new BT nodes or subtrees, reviewing existing nodes
for idiom conformance, or learning the canonical BT construction style.

**`embargo-default-semantics.md`**
Design decisions for `specs/embargo-policy.yaml` EP-04: default embargo state
(MUST produce `EM.ACTIVE`, not `EM.PROPOSED`), atomic PROPOSE+ACCEPT sequence,
and default embargo duration semantics.
**Load when**: implementing or debugging `InitializeDefaultEmbargoNode`, or
working on EP-04-001/EP-04-002 requirements (TASK-EMDEFAULT).

**`do-work-behaviors.md`**
Scope analysis of "do work" BT behaviors: out-of-scope, not-implementable, and
partially-implementable items. Documents the embargo policy prior art and the
`VulnerabilityDisclosurePolicy` wrapper concept.
**Load when**: evaluating scope of a new Do Work behavior, implementing policy
injection patterns, or scoping BT subtrees that depend on external policy
configuration.

---

## Case and Data Model

**`case-state-model.md`**
VFD/PXA case state hypercube, potential actions per state, measuring CVD
quality, participant-specific vs participant-agnostic state, append-only
`CaseStatus`/`ParticipantStatus` history model, `CaseEvent` trusted-timestamp
design (SC-PRE-1), actor-to-participant index (SC-PRE-2), report-as-proto-case
lifecycle, pre-case event backfill, and multi-vendor action rules.
**Load when**: working with case state machines, implementing participant or
embargo status transitions, adding `record_event()` calls, or debugging action
rule filtering.

**`case-log-authority.md`**
Assertion recording model for report / proto-case / case flows: implicit
participant assertions, `CaseActor`-authored `CaseLogEntry`, local audit log
vs replicated canonical chain, and rejection handling.
**Load when**: implementing case event logging, designing trust boundaries for
multi-actor case state synchronization, or evaluating the CaseActor assertion
model.

**`sync-log-replication.md`**
Log-centric architecture overview: hash-chain design rationale, log position
in activity `context`, implementation phases (SYNC-1–4), system invariants,
and open questions for the replicated case event log.
**Load when**: designing multi-actor case synchronization, evaluating the
hash-chain log approach, or scoping the SYNC-1–4 implementation phases.

**`participant-case-replica.md`**
Design notes for participant case replicas: per-actor case copies, the
synchronisation model between `CaseActor` and participant actors, and the
relationship to SYNC-1/SYNC-2 implementation phases.
**Load when**: implementing participant-side case replica handling, working on
`specs/participant-case-replica.yaml` (PCR) requirements, or designing the
`Announce(CaseLogEntry)` inbound handler.

**`participant-embargo-consent.md`**
Design decisions for per-participant embargo acceptance tracking: a 5-state
consent machine (`NO_EMBARGO → INVITED → SIGNATORY / DECLINED / LAPSED`),
embargo meta-protocol delivery to `DECLINED`/`LAPSED` participants, and the
`Accept(Invite(case))` → implicit consent rule. Not yet implemented.
**Load when**: implementing per-participant EM state tracking, working on the
embargo consent state machine in `vultron/core/states/`, or debugging
`embargo_adherence` field semantics.

---

## Codebase, Infrastructure, and Demos

**`codebase-structure.md`**
Module conventions and known gaps: enum refactoring, `vultron_types.py` split
(TECHDEBT-14), `CVDRoles` design decision, BT module boundary (`vultron/bt/`
vs `vultron/core/behaviors/`), demo script patterns (`demo_step` /
`demo_check`), docstring/markdown compatibility, `_shared_dl` router test
pattern, and circular import fix patterns.
**Load when**: adding or moving modules, writing router tests, debugging
import errors, or following established code organization conventions.

**`triggerable-behaviors.md`**
Design notes for PRIORITY-30 trigger endpoints: trigger scope, endpoint
schema, candidate RM/EM behaviors, per-participant embargo acceptance
tracking, resolved design decisions (P30-1–P30-3: outbox diff strategy,
procedural vs BT selection), and the BT requirement for trigger use cases.
**Load when**: implementing or modifying a trigger endpoint, designing the
request/response schema for a new trigger, or verifying whether a trigger use
case requires a BT.

**`docker-build.md`**
Project-specific Docker build observations: dependency layer caching, image
content scoping, health check coordination between services, and a general
build performance checklist.
**Load when**: modifying `docker/` files, debugging Docker Compose service
startup issues, or optimizing image build times.

**`encryption.md`**
Encryption design notes: public-key discovery, decryption placement in the
inbound pipeline, outgoing encryption strategies, key rotation, and
implementation guidance.
**Load when**: implementing message encryption/decryption in the ActivityPub
inbox/outbox pipeline.

**`demo-future-ideas.md`**
Extended multi-actor demo scenario sketches: Two-Actor (Finder + Vendor),
Three-Actor (Finder + Vendor + Coordinator), MultiParty (ownership transfer).
Describes what each scenario would demonstrate and open design questions.
**Load when**: designing new demo scripts or extending the existing demo suite
beyond the current two-actor scenario.

**`demo-review-26042001.md`** *(archived)*
Point-in-time demo review from 2026-04-20: log analysis and root-cause
findings from the multi-actor, three-actor, and multi-vendor demo runs.
Architectural decisions captured here are superseded by individual notes files
and `plan/IMPLEMENTATION_NOTES.md` REVIEW-26042001.
**Load when**: reviewing the historical context for the 2026-04-20
architectural decisions (DR-01 through DR-14).

**`trigger-classification.md`**
Classification of demo-specific vs general-purpose triggers: trigger routing
rules, naming conventions, and `ActorConfig`-driven trigger dispatch guidance.
**Load when**: implementing a new trigger endpoint, deciding whether a trigger
is demo-specific or protocol-general, or working on trigger routing in
`vultron/adapters/driving/fastapi/routers/`.

---

## Project Management and Planning

**`plan-history-management.md`**
Authoritative rules for managing `plan/IMPLEMENTATION_PLAN.md` (PLAN) and
history entries written to `plan/history/` (HISTORY): Core Invariant (no DONE
tasks in PLAN), No Tombstones rule, atomic two-phase completion protocol,
bounded PLAN size (≤ 20 tasks), failure modes, and entry formats.
**Load when**: completing a task and updating PLAN/HISTORY, reviewing the
`plan/history/` archive, or auditing PLAN for stale completed items.

**`plan-organization.md`**
Conventions for `plan/IMPLEMENTATION_PLAN.md` section structure and
`plan/PRIORITIES.md` coupling: `TASK-FOO` section IDs, dot-notation task IDs,
`TASK-` namespace to avoid spec-prefix collisions, migration examples, and
guidance for choosing a new `TASK-FOO` identifier.
**Load when**: adding a new section to IMPLEMENTATION_PLAN.md, assigning
or changing priorities, auditing plan sections for old priority-heading or
dash-notation task IDs.

**`history-management.md`**
Design decisions and implementation guidance for the chunked per-entry history
file system introduced on 2026-04-28. Covers the `plan/history/YYMM/<type>/`
directory layout, the `append-history` CLI tool, immutability rules, and
the migration from monolithic `plan/*HISTORY.md` files.
**Load when**: using or modifying the `append-history` tool, adding a new
`HistoryEntryType`, or understanding the `plan/history/` directory structure.

**`work-granularity.md`**
Design decisions for scoping implementation tasks to approximately one GitHub
Issue or PR. Decision table for when to split vs. group tasks, guidance on
coordinating with GitHub Issues, and the `TASK-FOO` ↔ Issue linking convention.
**Load when**: sizing a new TASK-FOO section, deciding whether to split or
merge tasks, or setting up GitHub Issue tracking for a planned work item.

**`append-only-file-handling.md`** *(archived — see `archived_notes/`)*
Superseded by `specs/history-management.yaml` and the `append-history` tool
(2026-04-28). The manual `cat >>` append procedure it describes is no longer
used.
**Load when**: investigating the pre-2026-04-28 history file procedure for
historical context only.

**`bugfix-workflow.md`**
Design decisions and implementation patterns for the test-first bugfix
workflow: the structured interview → failing-test → fix → verify cycle.
Operationalises `specs/bugfix-workflow.yaml` (BFW).
**Load when**: following the BUGFIX skill workflow, implementing bugfix
tooling, or working on BFW spec requirements.

**`agentic-workflow.md`**
The four-skill agentic development pipeline: `ingest-idea`, `learn`,
`update-plan`, and `build`. Documents the inputs, outputs, and trigger
conditions for each skill, and the priority-interrupt loop that governs
execution order (design > learn > plan > build). Includes a Mermaid
flowchart and future BT automation notes.
**Load when**: understanding or evolving the agent skill pipeline, automating
the development loop, or deciding which skill to run next.

---

## Documentation and Traceability

**`diataxis-framework.md`**
Documentation standards adapted from the Diátaxis model (Tutorials, How-to,
Reference, Explanation) applied to Vultron. Includes the documentation
compass and a workflow for authoring new technical docs.
**Load when**: writing new user-facing docs in `docs/`, or deciding which doc
type (tutorial / how-to / reference / explanation) a new page should be.

**`documentation-strategy.md`**
Docs chronology and trust levels, process models, formal protocol reference,
behavior simulator reference, Do Work behaviors, and ISO crosswalks.
**Load when**: evaluating where new documentation belongs, or cross-referencing
Vultron docs to ISO/CVD process standards.

**`user-stories-trace.md`**
Traceability matrix (111 stories, ~1,050 lines) mapping user stories from
`docs/topics/user_stories/` to formal requirements in `specs/`. A ToC at the
top indexes by story group (Reporting, Policy, Embargo, Case Mgmt, Identity,
Communication, Publication, Bug Bounty, Prioritization).
**Load when**: verifying requirement coverage for a user story, identifying
gaps between user stories and spec requirements, or reviewing story-to-spec
traceability.

**`notes-frontmatter.md`**
Design decisions for YAML frontmatter schema in `notes/*.md` files: required
fields (`title`, `status`), valid `status` values, `superseded_by` rule, schema
Pydantic model, loader, pre-commit hook, and migration checklist.
**Load when**: adding frontmatter to a new notes file, modifying the frontmatter
schema, or debugging `validate-notes-frontmatter` pre-commit failures.

**`spec-registry.md`**
Design notes for the spec registry: converting `specs/*.md` files to
structured YAML governed by Pydantic models in `vultron/metadata/specs/`,
mirroring the `vultron/metadata/notes/` pattern.
**Load when**: adding a new spec YAML file, modifying the spec registry schema,
or debugging `spec-dump` output issues.

---

## Tooling and Diagramming

**`mermaid-sequence-diagrams.md`**
Complete syntax reference for Mermaid sequence diagrams: participants,
actors and stereotypes, aliases, actor creation/destruction, grouping,
all arrow types (standard, half-arrow, bidirectional), activations, notes,
loops, alt/opt, parallel, critical regions, break, background highlighting,
comments, entity codes, sequence numbers, actor menus, CSS classes, and
configuration parameters. Includes a quick-reference composite example.
**Load when**: authoring or reviewing sequence diagrams in `docs/`, creating
protocol flow diagrams, or looking up a specific Mermaid sequence syntax detail.

---

## Conventions

- Each file focuses on a specific topic area.
- Write insights as **durable guidance for future agents** (not status
  reports).
- When a lesson is learned during implementation, add it here (not just in
  `plan/BUILD_LEARNINGS.md`).
- Cross-reference from `AGENTS.md` where relevant.
- **Update this README** whenever a file is added to or removed from `notes/`,
  or when a file's scope changes significantly
  (see `specs/project-documentation.yaml`).

## Relationship to plan/BUILD_LEARNINGS.md

`plan/BUILD_LEARNINGS.md` is **ephemeral** — it is a queue of raw observations
from build/bugfix runs, processed and deleted by the `learn` skill.
**Do not reference it from `AGENTS.md`** or from `notes/` files.

When updating `AGENTS.md`:

- Pull durable technical guidance from `notes/` (this directory), not from
  `plan/BUILD_LEARNINGS.md`.
- If `plan/BUILD_LEARNINGS.md` contains insights worth preserving, the `learn`
  skill promotes them here first; only then reference `notes/` from `AGENTS.md`.
