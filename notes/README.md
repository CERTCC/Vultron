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

**`architecture-hexagonal.md`**
Hexagonal architecture overview: layer model (core / wire / adapters), inbound
and outbound pipelines, The Hexagon diagram, file layout, Rules 1–10, design
constraints/invariants, and review checklist. Includes the
validate-at-edge / promote-to-core rule (ADR-0032).
**Load when**: orienting to architecture boundaries, reviewing layering
violations, or validating core/wire separation.

**`domain-validation.md`**
Strict vs. loose domain object boundary contract: where objects transition from
loose (wire-deserialized, possibly-None fields) to strict (all required fields
resolved), fail-fast patterns at use-case, BT node, and helper boundaries,
canonical helper locations (`use_cases/_helpers.py`), and the named
silent-failure sites from CONCERN-1360 with before/after behavior.
Normative requirements: `specs/architecture.yaml` ARCH-15-001 through
ARCH-15-004.
**Load when**: implementing or reviewing error handling in use cases or BT nodes,
auditing helpers that return `None` on failure, or designing new domain helpers
that require non-None inputs.

**`vultron/core/ports/AGENTS.md`**
Port-focused architecture guidance for `vultron/core/ports/`: inbound vs
outbound port taxonomy, dispatch-vs-emit terminology,
use-cases-as-incoming-ports guidance, named ports
(`SyncActivityPort`, `TriggerActivityPort`), server-level inbox deferred
design, and DataLayer design rules.
**Load when**: working in `vultron/core/ports/`, clarifying dispatch/emit
semantics, designing new port interfaces, or debugging DataLayer
boundaries and auto-rehydration.

**`architecture-adapters.md`**
Adapter-focused architecture guidance: adapter category discipline, outbound
delivery invariants, ASGI emitter patterns, driven-port baton-pass pattern,
long-term BT flow direction, remaining ARCH-01-001 violation context, future
delivery stubs, boundary ratchet tests, and DataLayer scope boundaries.
**Load when**: implementing adapters, debugging delivery behavior, or auditing
adapter/core boundary compliance.

**`vultron/adapters/driven/AGENTS.md`**
Design rules for `ASGIEmitter` and other driven-adapter delivery details:
scheme+netloc-only local ASGI delivery, `mount_prefix` stripping,
per-app `create_app()` isolation, and co-located actor DataLayer
isolation.
**Load when**: implementing or debugging `ASGIEmitter`, wiring up
co-located actors in the same process, or investigating ASGI delivery
404s or cross-actor data leakage.

**`domain-model-separation.md`**
Analysis of the current coupling between wire format (ActivityStreams), domain
logic, and persistence in `VulnerabilityCase`. Documents the recommended
three-layer separation and migration path, DataLayer isolation options (now
superseded by Priority 325), and `FooActivity` vs `FooEvent` naming. Includes
post-P75-2 architectural findings.
**Load when**: refactoring `VulnerabilityCase` or related models, evaluating
DataLayer backends, or planning domain/wire layer decoupling.

**`datalayer-design.md`**
DataLayer architecture notes: `DataLayer` vs. `CasePersistence` narrowing,
deprecated `get()`/`by_type()` methods, `CaseOutboxPersistence` as a smell
marker, auto-rehydration contract (`dl.read()` MUST return typed objects),
storage record re-evaluation, and vocabulary registry entanglement. Operating
rules are in `vultron/core/ports/AGENTS.md`.
**Load when**: working on `DataLayer` adapters, `CasePersistence` protocol,
rehydration of nested objects, or storage record migration.

**`vultron/wire/as2/factories/AGENTS.md`**
Factory-function operating rules for outbound Vultron protocol activities.
See `notes/activity-factories.md` for the full design rationale and inventory.
**Load when**: implementing outbound activity construction or debugging factory errors.

**`activity-factories.md`**
Full design rationale, factory inventory (all 31 factory functions with return
types and internal classes), migration guide, before/after call-site examples,
and testing patterns for the factory-function layer. Operating rules are in
`vultron/wire/as2/factories/AGENTS.md`.
**Load when**: implementing or migrating outbound activity construction, reviewing
the full factory inventory, or understanding the `VultronActivityConstructionError`
wrapping pattern.

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

**`inbox-orchestration.md`**
Design decisions for the core BT-backed inbox orchestration module: why
orchestration belongs in `core/`, two-adapter seam design
(`IngressPayloadAdapter` + `DispatchAdapter`), BT node ordering invariant,
`InboxOutcome` contract, pending-queue port injection, and migration path
from the existing `InboxPipeline`/`inbox_handler`.
**Load when**: implementing or modifying the inbox pipeline, adding a new
entry point (CLI, MCP) that processes inbound activities, or debugging
`process_payload` behavior.

**`vultron/wire/as2/vocab/AGENTS.md`**
Vocabulary registry design rules: `__init_subclass__` auto-registration,
flat dict structure, `VocabNamespace` metadata, `Literal type_`
detection for concrete classes, fail-fast unknown-type handling, and the
migration path.
**Load when**: adding new ActivityStreams vocabulary types, modifying
registry decorators, or diagnosing vocabulary type-resolution issues.

**`federation_ideas.md`**
Open design exploration: AS2 as vocabulary (not full ActivityPub), actor /
inbox / outbox model, case object ownership, relay pattern, journal vs delivery
log, mirror consistency, instance trust, peering handshake, connector plugins.
**Load when**: scoping multi-instance federation, designing actor peering, or
evaluating the relay/journal delivery architecture.

---

## Protocol Conformance and Behavioral Specs

**`behavioral-conformance-specs.md`**
Design rationale and implementation plan for the behavioral conformance spec
layer (RMB, EMB, CSB): ECA rules, schema extensions (`TriggerType`, `Trigger`,
typed `Precondition`), conformance level framing (L1–L4), PR sequence, and
primary sources for spec content.
**Load when**: implementing or reviewing `specs/rm-behavior.yaml`,
`specs/em-behavior.yaml`, or `specs/cs-behavior.yaml`; extending the spec
schema for behavioral specs; or drafting docs updates for behavior logic.

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

**`case-proposal.md`**
Design rationale, protocol flow, and implementation guidance for the
`CaseProposal` mechanism: new `as_CaseProposal` AS2 object type, the
`Create(CaseProposal)` / `Accept(CaseProposal)` / `Reject(CaseProposal)` flow,
`ProposeCaseToActorNode` vs `CreateCaseActorNode` responsibilities, and the
three received-side use cases. ADR: `docs/adr/0023-case-proposal-protocol.md`.
**Load when**: implementing `as_CaseProposal`, `ProposeCaseToActorNode`, or
the received-side use cases; or working on issues #810, #811, #812.

**`vocabulary-registry.md`**
Design decisions and migration path for the AS2 vocabulary registry refactor:
auto-registration via `__init_subclass__`, flat registry dict, `VocabNamespace`
enum, fail-fast on unknown types, and dynamic discovery at startup. Operating
rules are in `vultron/wire/as2/vocab/AGENTS.md`.
**Load when**: adding new vocabulary classes, debugging deserialization failures,
or planning the `@activitystreams_object` decorator removal migration.

**`vultron/wire/as2/AGENTS.md`**
Wire-layer semantic extraction guidance: pattern ordering invariant,
import-time `_validate_registry_order()` guard, file locations, and the
checklist for adding a new `ActivityPattern`.
**Load when**: adding or debugging a `SemanticEntry`, investigating a
wrong-handler dispatch, or reasoning about pattern ordering.

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

**`peer-broadcast-failure-semantics.md`**
Fail-fast requirements for protocol-visible peer fan-out in BT paths:
broadcast preparation/enqueue errors must return `FAILURE`, and success
fallbacks must not mask delivery failure. Includes scope boundaries for this
phase and shared-helper guidance.
**Load when**: modifying status/embargo broadcast paths, defining fan-out
error behavior, or planning delivery-reliability follow-on work.

**`bt-composability.md`**
Fractal composability pattern for BT nodes and subtrees (formerly split between
`bt-composability.md` and `bt-reusability.md`): the "trunkless branch" model,
parameterization guidelines, anti-patterns (hard-coded actor roles, demo-specific
logic in nodes, one-off subtrees, duplicated logic), and a composability checklist.
Operationalizes `specs/behavior-tree-node-design.yaml` (BTND-01 through BTND-04).
**Load when**: designing a new BT node or subtree, auditing existing nodes for
composability violations, or refactoring near-duplicate BT implementations.

**`bt-fuzzer-nodes.md`**
Index and background for the fuzzer node catalog. Fuzzer nodes are stub
implementations in the legacy BT simulation (`vultron/bt/`) that stand in for
real-world decision logic not yet implemented. Each fuzzer node is a
**call-out point** — a location where the BT cannot proceed automatically and
needs external input (data, a decision, or content). This file explains the
entry format, automation potential categories, and the fuzzer base-type
probability table, then indexes the per-domain sub-files.
**Load when**: understanding what fuzzer nodes are and why they exist; mapping
fuzzer nodes to coordination agent types; jump directly to a sub-file for the
actual catalog entries.

**`bt-fuzzer-nodes-vul-discovery.md`**
Fuzzer node catalog for the Vulnerability Discovery workflow
(`vultron/bt/vul_discovery/`): `HaveDiscoveryPriority`, `DiscoverVulnerability`,
`NoVulFound`.
**Load when**: replacing fuzzer stubs in the vulnerability discovery BT.

**`bt-fuzzer-nodes-embargo.md`**
Fuzzer node catalog for the Embargo Management workflow
(`vultron/bt/embargo_management/`): all exit-trigger, proposal/counter,
acceptance/rejection, and timer nodes.
**Load when**: replacing fuzzer stubs in the embargo management BT.

**`bt-fuzzer-nodes-report-management.md`**
Fuzzer node catalog for all Report Management workflows
(`vultron/bt/report_management/`): validation, prioritization, ID assignment,
fix development/deployment, exploit/threat tracking, publication,
reporting-to-others, and report closure nodes.
**Load when**: replacing fuzzer stubs in any report management BT subtree.

**`bt-fuzzer-nodes-messaging.md`**
Fuzzer node catalog for the Inbound Message Handling workflow
(`vultron/bt/messaging/`): `FollowUpOnErrorMessage`.
**Load when**: replacing fuzzer stubs in the inbound message handling BT.

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

**`lifecycle-staged-types.md`**
Design guidance for lifecycle-staged domain types (ADR-0033): the field-set
governing principle (a milestone earns a type only when it changes the
guaranteed-field set), the three-class analysis (only `VulnerabilityCase` gets
staged types — `IncomingReport` → `Case` → `EmbargoedCase`; `ParticipantStatus`
and `CaseStatus` use predicates + state groups), the `model_validate`-at-edge
read mechanism, the data-as-source-of-truth transition model, the DataLayer
round-trip constraint, and the per-dimension-status decomposition trailhead.
**Load when**: designing or reviewing staged domain types, deciding whether a
lifecycle milestone should be a type vs. a predicate/precondition, or working on
`specs/lifecycle-staged-types.yaml` (LST) requirements.

**`case-state-model.md`**
VFD/PXA case state hypercube, potential actions per state, measuring CVD
quality, participant-specific vs participant-agnostic state, append-only
`CaseStatus`/`ParticipantStatus` history model, actor-to-participant index
(SC-PRE-2), report-as-proto-case lifecycle, pre-case event backfill, and
multi-vendor action rules. Note: `CaseEvent`/`record_event()` were removed
in issue #792; all protocol-significant history now lives in the canonical
`CaseLedgerEntry` hash chain.
**Load when**: working with case state machines, implementing participant or
embargo status transitions, or debugging action rule filtering.

**`case-communication-model.md`**
Canonical communication model for post-case-creation participant messaging:
all messages route through the Case Actor only
(`participant → CaseActor → CaseLedgerEntry → broadcast → participants`). Covers
the routing rule, its rationale, the `case_addressees()` antipattern, how to
resolve the Case Actor ID, and the automatic `CaseLedgerEntry + broadcast`
cascade. Normative requirements: `specs/participant-case-replica.yaml` PCR-08.
**Load when**: implementing any trigger use case or BT that causes a
participant to send a case-scoped message, debugging out-of-band note or
embargo delivery, or auditing outbound activity addressing.

**`case-ledger-authority.md`**
Assertion recording model for report / proto-case / case flows: implicit
participant assertions, `CaseActor`-authored `CaseLedgerEntry`, local audit log
vs replicated canonical chain, and rejection handling.
**Load when**: implementing case event logging, designing trust boundaries for
multi-actor case state synchronization, or evaluating the CaseActor assertion
model.

**`sync-ledger-replication.md`**
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
`Announce(CaseLedgerEntry)` inbound handler.

**`participant-embargo-consent.md`**
Design decisions for per-participant embargo acceptance tracking: a 5-state
consent machine (`NO_EMBARGO → INVITED → SIGNATORY / DECLINED / LAPSED`),
embargo meta-protocol delivery to `DECLINED`/`LAPSED` participants, and the
`Accept(Invite(case))` → implicit consent rule. Not yet implemented.
**Load when**: implementing per-participant EM state tracking, working on the
embargo consent state machine in `vultron/core/states/`, or debugging
`embargo_adherence` field semantics.

**`embargo-lifecycle.md`**
Target architecture for EM state management: the inline-`EMAdapter`
instantiation anti-pattern, the current fragmentation across trigger use cases,
received use cases, and BT behaviors, and the planned `EmbargoLifecycle`
service (#538) that will consolidate all EM + PEC transitions.
**Load when**: implementing any embargo state transition in trigger or received
use cases, designing the `EmbargoLifecycle` service (#538), auditing inline
`create_em_machine()` instantiations, or working on the post-#538
`triggers/embargo.py` cleanup (#516).

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
implementation guidance. Implementation is tracked in issue #1156.
**Load when**: implementing message encryption/decryption in the ActivityPub
inbox/outbox pipeline (see issue #1156 and its children).

**`demo-future-ideas.md`**
Extended multi-actor demo scenario sketches: Two-Actor (Finder + Vendor),
Three-Actor (Finder + Vendor + Coordinator), MultiParty (ownership transfer).
Describes what each scenario would demonstrate and open design questions.
**Load when**: designing new demo scripts or extending the existing demo suite
beyond the current two-actor scenario.

**`vultron/core/use_cases/triggers/AGENTS.md`**
Trigger classification guidance: demo-specific vs general-purpose
triggers, `/demo/` vs `/trigger/` routing, `RunMode`, wrapper patterns,
audit results, and trigger-layer import rules.
**Load when**: implementing a new trigger endpoint, deciding whether a
trigger is demo-specific or protocol-general, or working on trigger
routing in `vultron/adapters/driving/fastapi/routers/`.

**`triggers-test-coverage.md`**
Coverage expectations for trigger use cases in
`vultron/core/use_cases/triggers/` and PR-scope discipline for files that
co-evolve with embargo logic. Anchors which trigger use cases have dedicated
tests and which are missing.
**Load when**: adding a trigger use case, modifying `triggers/case.py` or
`triggers/embargo.py`, or scoping a PR that touches both case and embargo
triggers.

---

## Project Management and Planning

**`history-management.md`**
Design decisions and implementation guidance for the chunked per-entry history
file system introduced on 2026-04-28. Covers the `plan/history/YYMM/<type>/`
directory layout, the `append-history` CLI tool, immutability rules, and
the migration from monolithic `plan/*HISTORY.md` files.
**Load when**: using or modifying the `append-history` tool, adding a new
`HistoryEntryType`, or understanding the `plan/history/` directory structure.

**`plan-history-management.md`** *(archived — see `archived_notes/`)*
Superseded by `specs/history-management.yaml` and the `append-history` tool.
The IMPLEMENTATION_PLAN.md management rules it described are no longer relevant.

**`plan-organization.md`** *(archived — see `archived_notes/`)*
Superseded — described the now-retired `TASK-FOO` naming scheme for
`plan/IMPLEMENTATION_PLAN.md`. All work is tracked as GitHub Issues.
See `notes/parallel-development.md` for the current model.

**`work-granularity.md`** *(archived — see `archived_notes/`)*
Superseded — described the three-tier model (GitHub Issue → TASK-FOO →
checklist items). IMPLEMENTATION_PLAN.md has been removed; see
`specs/project-documentation.yaml` PD-09 for current guidance.

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

**`coordination-agents.md`**
Design guidance for coordination agents — external capabilities (human, skill,
or LLM agent) that answer Vultron call-out points. Covers the two-surface
integration model (trigger endpoints = call-in; call-out points = call-out),
the four agent type patterns (Sentinel, Evaluator, Retriever, Composer), the
trust/execution-authority axis, composite agent design, and the fuzzer-node
discovery methodology.
**Load when**: designing a new coordination agent or call-out point integration,
working on the fuzzer-to-agent replacement roadmap, or explaining the
coordination agent concept to new contributors.

**`agents-md-structure.md`**
Routing policy for `AGENTS.md` content: the decision tree for whether new
guidance belongs in root `AGENTS.md`, a per-directory `AGENTS.md` file
(e.g., `vultron/core/`, `vultron/wire/as2/`, `vultron/adapters/`, `test/`),
or a `notes/<topic>.md` design note. Explains the 400-line threshold for
root AGENTS.md and the migration pattern using `condense-agents-md`.
**Load when**: adding a new pitfall or convention to any AGENTS.md file,
deciding where to place new agent guidance, or running `condense-agents-md`.

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

**`notes-frontmatter.md`**
Design decisions for YAML frontmatter schema in `notes/*.md` files: required
fields (`title`, `status`), valid `status` values, `superseded_by` rule, schema
Pydantic model, loader, pre-commit hook, and migration checklist.
**Load when**: adding frontmatter to a new notes file, modifying the frontmatter
schema, or debugging `validate-notes-frontmatter` pre-commit failures.

**`spec-registry.md`** *(archived — see `archived_notes/`)*
Implemented — `specs/*.md` fully migrated to YAML; `vultron/metadata/specs/` is in place.

**`demo-ci.md`** *(archived — see `archived_notes/`)*
Implemented — `demo-integration.yml` workflow exists in `.github/workflows/`.

**`docs-build-workflow.md`** *(archived — see `archived_notes/`)*
Implemented — `docs-build-check.yml` workflow exists in `.github/workflows/`.

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
