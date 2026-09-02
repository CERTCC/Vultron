# Design Insights and Implementation Notes

This directory captures **durable design insights** for the Vultron project.
Unlike `plan/BUILD_LEARNINGS.md` (which is ephemeral), files here are
committed to version control and MUST be kept up to date as the
implementation evolves.

Archived notes sections (fully superseded or completed task logs) are in
`plan/history/YYMM/note/` — archived via `append-history note` with source ID
`NOTES-<file-stem>--<section-slug>`.

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

**`core-wire-rendering-port.md`**
Why core legitimately needs wire-shaped JSON (only for
`CaseLedgerEntry.payloadSnapshot`), why `alias_generator=to_camel` on core types
was both an ARCH-12-003 violation and structurally insufficient, and the
`WireRenderPort` driven seam that replaces it. Lists the five consumers of the
old core-side aliasing, the reject-guard that MUST accompany deletion of any
flat-field shim (SDO-03-005), and why persisted rows are unaffected.
The decision stands but its **mechanism is revised by ADR-0082**: the adapter
resolves the counterpart through the pairing registry and delegates to the
adapter-side translator rather than calling `wire_cls.from_core()`. This port
covers only the **core→wire** half of ARCH-01-001; the mirror-image
`WireParsePort` (ADR-0082) covers wire→core. Design rationale for both:
`notes/wire-core-boundary.md`.
Normative requirements: `specs/architecture.yaml` ARCH-20,
`specs/case-ledger-processing.yaml` CLP-07-009/010.
**Load when**: touching `alias_generator`/`by_alias` anywhere, building or
reviewing payload snapshots, removing a flat-field migration shim, or adding a
core→wire projection.

**`domain-validation.md`**
Strict vs. loose domain object boundary contract: where objects transition from
loose (wire-deserialized, possibly-None fields) to strict (all required fields
resolved), fail-fast patterns at use-case, BT node, and helper boundaries,
canonical helper locations (`use_cases/_helpers.py`), and the named
silent-failure sites from CONCERN-1360 with before/after behavior. Also records
why rejecting an input as a unit does **not** license reporting only the first
violation, the root-vs-derived classification for multi-violation reports, and
why the trigger path fails closed while the receive path partial-accepts — the
two halves of Postel's maxim, not an inconsistency to reconcile (ADR-0084).
Normative requirements: `specs/architecture.yaml` ARCH-15-001 through
ARCH-15-004; `specs/error-handling.yaml` EH-05-002, EH-07.
**Load when**: implementing or reviewing error handling in use cases or BT nodes,
auditing helpers that return `None` on failure, designing new domain helpers
that require non-None inputs, or deciding how much diagnostic detail a
validation boundary owes its caller.

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
delivery invariants, the uniform-HTTP inter-actor delivery model (ADR-0042),
driven-port baton-pass pattern, long-term BT flow direction, remaining
ARCH-01-001 violation context, future delivery stubs, boundary ratchet tests,
and DataLayer scope boundaries.
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
DataLayer architecture notes: **per-actor storage isolation (ADR-0073)** — one
store per hosted actor, holding only that actor's knowledge, resolved by
`get_datalayer(actor_id)`; `DataLayer` vs. `CasePersistence` narrowing,
deprecated `get()`/`by_type()` methods, `CaseOutboxPersistence` as a smell
marker, auto-rehydration contract (`dl.read()` MUST return typed objects),
storage record re-evaluation, and vocabulary registry entanglement. Operating
rules are in `vultron/core/ports/AGENTS.md`.
**Load when**: working on `DataLayer` adapters, `CasePersistence` protocol,
resolving which store a read or write belongs to, rehydration of nested
objects, or storage record migration.

**`wire-artifact-immutability.md`**
Design principle for wire Activity immutability: received artifacts MUST be
frozen at receipt (A/B split — A = frozen ledger snapshot, B = separately
constructed hydrated routing copy); emitted blobs MUST be frozen by the factory
and used unchanged as both `payloadSnapshot` and delivery payload; ports are
dumb relays (no adapter enrichment). Covers the orthogonality of lenient field
types (`validate_assignment=False`) and post-construction immutability
(`frozen=True`). Spec requirements: `VM-08-002`, `VM-08-003`.
**Load when**: implementing or reviewing the inbound pipeline (inbox freeze
point), outbound factory/port interfaces (`TriggerActivityPort`,
`SyncActivityPort`), `CaseLedgerEntry.payloadSnapshot` construction, or
auditing `outbox_delivery.py` for enrichment mutations. Source: CONCERN-2545.

**`wire-core-boundary.md`**
The wire/core boundary contract (ADR-0082): one declarative core↔wire pairing
registry, one generic bidirectional translator on the adapter side, and
`extra="forbid"` on the core branch as the structural guarantee. Explains why
ARCH-01-001 (core→wire) and ARCH-22-001 (wire→core) are *different* rules and
why ADR-0063 solved only the first; why "zero wire→core imports" was
unreachable; the four duplications the pairing registry replaces; and the
measured blast radii (25 vs 570 failures) with the `embargo_adherence`
computed-field and `id_` round-trip findings. Also records which half of
`as_ObjectRef` is AS2-faithful and which half is a kludge.
**Load when**: touching core↔wire translation, the vocabulary registries,
`_field_map`/`from_core`/`to_core`, the ARCH-22 import ratchet, or adding a
validator that raises on a core-branch type. Source: G02 / CONCERN-2830.

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

**`outbox-delivery-reliability.md`**
Implementation guidance for the outbox delivery reliability hardening (CONCERN-2302 /
ADR-0066): per-activity abort scope fix, 4xx terminal classification, timeout/jitter/pool
configuration, and per-activity attempt counter with dead-letter store.
**Load when**: implementing Tasks for #2302 (abort scope, 4xx classification,
timeout/jitter/limits, attempt counter, dead letter), or adding new delivery paths that
must satisfy OX-13-001 through OX-13-006.

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

**`structured-logging.md`**
Narrative log template (SL-04-006), infrastructure demotion list (SL-04-007),
and per-module guidance for keeping actor INFO logs readable as a CVD protocol
story. Documents the approved verb–template inventory (`Actor '<id>' RM: A → B
for case '<id>'`), the ~10 infrastructure patterns that MUST be at DEBUG, and
the ~8 missing INFO messages required by SL-04-001. Source: CONCERN-1968.
**Load when**: adding a new BT node that writes RM/CS/EM state (must add INFO
log), auditing logging levels in actor container output, or implementing
CONCERN-1968 logging remediation.

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

**`use-case-protocol.md`**
Design decisions for the `UseCaseResult` type hierarchy (`HandlerResult` /
`TriggerResult`), the two semantically distinct request paths (`VultronEvent`
vs `TriggerRequest`), why `UseCaseRequest` was not introduced, how
`TriggerService` and `TriggerServicePort` were migrated from `dict` to
`TriggerResult`, and the ratchet test design. ADR: `docs/adr/0040-use-case-result-envelope.md`.
**Load when**: implementing a new use case, reviewing the `execute()` contract,
working on `UseCase` Protocol or `TriggerServicePort` signatures, or debugging
return-type ratchet failures.

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
`rehydrate()` patterns, asymmetric inbox routing, embargo-as-calendar-invitation,
vocabulary examples, and re-engagement patterns.
**Load when**: implementing any inbound or outbound message handler, debugging
semantic extraction, or writing new ActivityStreams vocabulary classes.

**`activitystreams-state-update.md`**
Advanced ActivityStreams design notes: Case State update path, `CaseActor`
authoritativeness, DR-series named bugs (DR-02, DR-05, DR-07, DR-08–DR-14),
transitive activity patterns, base-typed serialization, invite response
parsing, bootstrap embedded-object contract, semantic registry patterns,
and `offer_case_participant_activity` object-id semantics.
**Load when**: debugging AS2 state-update paths, investigating named DR-series
bugs, working on transitive activity dispatch, or tracing case-state divergence.

**`case-proposal.md`**
Design rationale, protocol flow, and implementation guidance for the
`CaseProposal` mechanism: new `as_CaseProposal` AS2 object type, the
`Create(CaseProposal)` / `Accept(CaseProposal)` / `Reject(CaseProposal)` flow,
`ProposeCaseToActorNode` vs `CreateCaseActorNode` responsibilities, the
three received-side use cases, and the `case_actor_service_url` configuration
invariant for `ResolveCaseActorUrlsNode` (CP-08-001 through CP-08-003).
ADR: `docs/adr/0023-case-proposal-protocol.md`.
**Load when**: implementing `as_CaseProposal`, `ProposeCaseToActorNode`,
`ResolveCaseActorUrlsNode`, or the received-side use cases; or working on
issues #810, #811, #812, #1633, #1640.

**`vocabulary-registry.md`**
Design decisions and migration path for the AS2 vocabulary registry refactor:
auto-registration via `__init_subclass__`, flat registry dict, `VocabNamespace`
enum, fail-fast on unknown types, and dynamic discovery at startup. Operating
rules are in `vultron/wire/as2/vocab/AGENTS.md`. `VOCABULARY` (keyed by full
`as_*` class name) and `WIRE_TYPE_MAP` (keyed by wire `type_` value) are
disjoint, so a core type's wire counterpart is resolved through `WIRE_TYPE_MAP`,
never by name coincidence (ARCH-23-002). The declarative pairing registry that
supersedes both lookups (ARCH-23-001) is still pending — issue #2937.
**Load when**: adding new vocabulary classes, debugging deserialization failures,
resolving a core type's wire counterpart, or planning the
`@activitystreams_object` decorator removal migration.

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
Core BT design decisions: when to use BTs vs procedural code, py_trees
patterns, simulation-to-prototype translation strategy, actor isolation,
concurrency model, RM state machine context, EvaluateCasePriority direction,
composability, and open architecture questions.
**Load when**: making architecture decisions about BT structure, deciding
whether a new use case needs a BT, or implementing a BT-backed use case
from scratch.

**`py-trees-ports-adoption.md`** *(archived — migration complete)*
Completed reference for the py_trees 2.5.0 typed-Ports migration
(`vultron/core/behaviors/`): the eight finalized conventions (Type A–D node
shapes, execution-scoped keys, read-modify-write dual-alias, `_InboxNodeWithPorts`
base, `NotImplementedError` on explicit `None`), the composite and
constructor-parameterized gate exemptions, and the planned XML-as-spec spike.
**Load when**: writing a new BT node that uses typed Ports and need the
canonical patterns reference (finalized conventions sections 1–8).
**Do not load when**: looking for live migration tasks — the migration
(`#1809` chain, parts 1–5) is complete.

**`bt-canonical-reference.md`**
Canonical CVD Protocol Behavior Tree structural reference: trunk-removed
branches model, node symbol legend, top-level structure, subtree map
(ReceiveMessagesBt, ReportManagementBt, EmbargoManagementBt), Prioritize
subtree detail, how to locate new behaviors in the canonical tree, key fuzzer
nodes, and the BT-IDM-01/02/03 anti-pattern reference (spec: BT-22-001/002/003).
**Load when**: locating where a cascade fits in the canonical BT, checking
whether a new behavior must be a subtree, diagnosing layer-boundary violations
(BT node calling use cases, importing from use_cases/), or auditing god nodes.

**`bt-pitfalls.md`**
Cross-cutting BT mechanics: failure reason propagation, blackboard lookup
semantics (`get()` raises on unwritten READ keys), `memory=False` partial-write
semantics, no-op path key clearing, blackboard key namespacing for concurrent
executions (BTND-03-004), `BTBridge.execute_with_setup` return value handling,
sentinel blackboard writes, and guard name / state-machine precondition
alignment. Domain-specific pitfalls live in per-directory `AGENTS.md` files
under `vultron/core/behaviors/`.
**Load when**: debugging a BT that returns unexpected FAILURE/SUCCESS, auditing
blackboard key race conditions, implementing a new BT node pattern, or
investigating cross-cutting mechanics that span multiple BT domains.

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

**`call-out-configuration.md`**
Design decisions for how running code selects backend factories for call-out
point nodes in BT tree builders: three-mode model (DETERMINISTIC /
STOCHASTIC / REAL), domain bundle dataclasses, pre-built singletons,
`CallOutBackendFactory` Protocol, default direction rule (ceiling/floor of
stochastic p), and the extension points for YAML/CLI config and personality
bundles. Derived from #1631 planning; implemented by #1152.
**Load when**: implementing or extending call-out point backend injection in
demo scenarios or tests; designing the bundle/singleton layout in
`vultron/demo/fuzzer/bundles/`; understanding the three-mode backend model.

**`protocol-asks.md`**
The protocol-ask primitive: why an actor asks and terminates rather than
suspending (nothing in the codebase returns `RUNNING`, and the bridge cannot host
it), the conversation-state routing tree shape, the outstanding-ask register and
why it never authorizes anything, per-ask-kind expiry with a Sentinel reaping
seam, and `Create(ProcessingFault)`. Names the two hand-built reference
implementations to generalise (`suggest_actor_tree.py`, `VultronOfferRecord`) and
the missing shared emit path that blocks all of it. Normative requirements:
`specs/protocol-asks.yaml` (ASK-01 through ASK-08). ADR: ADR-0080.
**Load when**: implementing or reviewing any gate that needs another actor's
permission, working on `RequireCaseOwnerApprovalNode` or the status authorization
gates, adding an ask/reply exchange, touching `find_protocol_pair` or
`PendingAssertionStore`, or implementing processing-fault notification.
Source: CONCERN-2829.

**`received-status-authorization.md`**
Two-gate design for received-side CaseStatus canonicalization: StatusAdoptionGate
(in `add_participant_status_tree`) for status adoption authorization,
EmbargoTeardownAuthorizationGate + ThreatTerminationBranchNode (in `add_case_status_tree`)
for embargo teardown. Documents CASE_OWNER gospel-bypass rationale, self-addressed
Add(CaseStatus) threading pattern, and migration from PublicDisclosureBranchNode.
Derived from IDEA-1836 / ADR-0046.
**Load when**: implementing #1836 or any changes to received-side status handling,
StatusAdoptionGate, EmbargoTeardownAuthorizationGate, or ThreatTerminationBranchNode;
understanding the sentinel actor integration pattern.

**`bt-fuzzer-nodes.md`**
Index and background for the fuzzer node catalog. Fuzzer nodes are stub
implementations in the legacy BT simulation (`vultron/bt/`) that stand in for
real-world decision logic not yet implemented. Each fuzzer node is a
**call-out point** — a location where the BT cannot proceed automatically and
needs external input (data, a decision, or content). This file explains the
entry format, automation potential categories, and the fuzzer base-type
probability table, then indexes the per-domain sub-files.
**Load when**: understanding what fuzzer nodes are and why they exist; mapping
fuzzer nodes to capability shapes; jump directly to a sub-file for the
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
Index file for all Report Management fuzzer-node catalogs. Contains the
fuzzer base-type probability table, per-workflow catalog links, and the
cross-cutting Production Collapse designs (collapses 1–4: exploit strategy,
publication intents, notification loop, publish pipeline) and sentinel-stub
sync guidance.
**Load when**: looking up Production Collapse designs, reviewing the
probability table, or navigating to a specific sub-workflow catalog.

**`bt-fuzzer-rm-validation.md`** — Report Validation (`RMValidateBt`): credibility/validity checks and new-info sentinels.
**Load when**: replacing fuzzer stubs in the report validation BT.

**`bt-fuzzer-rm-prioritization.md`** — Report Prioritization (`RMPrioritizeBt`): priority assessment and ranking nodes.
**Load when**: replacing fuzzer stubs in the report prioritization BT.

**`bt-fuzzer-rm-id-assignment.md`** — Vulnerability ID Assignment (`AssignVulIdBt`): CVE ID acquisition nodes.
**Load when**: replacing fuzzer stubs in the vulnerability ID assignment BT.

**`bt-fuzzer-rm-fix.md`** — Fix Development + Deployment (`DevelopFixBt` / `DeployFixBt`): patch creation and rollout nodes.
**Load when**: replacing fuzzer stubs in the fix development or deployment BT.

**`bt-fuzzer-rm-exploit.md`** — Exploit Acquisition (`AcquireExploitBt`): exploit-presence checks and strategy nodes.
**Load when**: replacing fuzzer stubs in the exploit acquisition BT.

**`bt-fuzzer-rm-threat.md`** — Threat Monitoring (`MonitorThreatsBt`): active-threat detection and escalation nodes.
**Load when**: replacing fuzzer stubs in the threat monitoring BT.

**`bt-fuzzer-rm-publication.md`** — Publication (`PublicationBt`): disclosure decisions, content preparation, and advisory nodes.
**Load when**: replacing fuzzer stubs in the publication BT.

**`bt-fuzzer-rm-reporting.md`** — Reporting to Other Parties (`ReportToOthersBt`): outbound-report and participant-tracking nodes.
**Load when**: replacing fuzzer stubs in the reporting-to-others BT.

**`bt-fuzzer-rm-closure.md`** — Report Closure + Other Work (`CloseReportBt` / `RMDoWorkBt`): close-case eligibility and extensibility stub nodes.
**Load when**: replacing fuzzer stubs in the report closure or other-work BT.

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
default embargo duration semantics, and the published-default / tacit-acceptance
model explaining why no EP/EA exchange appears on the happy path.
**Load when**: implementing or debugging `InitializeDefaultEmbargoNode`,
working on EP-04-001/EP-04-002 requirements, or distinguishing the default
embargo path from the negotiated path in demos or protocol traces.

**`do-work-behaviors.md`**
Scope analysis of "do work" BT behaviors: out-of-scope, not-implementable, and
partially-implementable items. Documents the embargo policy prior art and the
`VulnerabilityDisclosurePolicy` wrapper concept.
**Load when**: evaluating scope of a new Do Work behavior, implementing policy
injection patterns, or scoping BT subtrees that depend on external policy
configuration.

---

## Case and Data Model

**`status-dimension-objects.md`**
Design guidance for per-machine dimension objects decomposed from `CaseStatus`
and `ParticipantStatus` (ADR-0036): naming table, `BaseModel`-not-`CoreObject`
rationale, immutable `transition()` pattern, wire projection notes, call-site
migration mapping (~308 active sites), and `EmbargoLifecycle` migration priority.
**Load when**: implementing or reviewing dimension-object migration, working on
`specs/status-dimension-objects.yaml` (SDO) requirements, or understanding how
`EmDimension`/`RmDimension`/etc. embed inside status objects.

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

**`case-ledger-parsing.md`**
Tolerant parsing patterns for case-ledger JSONL consumers: the three nesting
shapes for RM/EM/VFD/PXA state (ADR-0036 dimension objects, legacy flat wire
spellings, nested-under-Add), robust extraction helpers, malformed-field
coercion, and multi-case partitioning (DRPT-02-006).
**Load when**: writing any consumer of case-ledger JSONL (report tools,
invariant checks, dashboards), debugging state extraction from devlogs, or
implementing `payloadSnapshot` parsers.

**`sync-ledger-replication.md`**
Log-centric architecture overview: hash-chain design rationale, log position
in activity `context`, implementation phases (AppendOnlyLedger–PeerLedgerSync), system invariants,
open questions for the replicated case event log, SYNC-13 ledger write-ownership
boundary, and pre-SYNC-13 upgrade path.
**Load when**: designing multi-actor case synchronization, evaluating the
hash-chain log approach, scoping the AppendOnlyLedger–PeerLedgerSync implementation phases, or
investigating the SYNC-12/SYNC-13 effects-before-persist and write-ownership
invariants.

**`participant-case-replica.md`**
Design notes for participant case replicas: per-actor case copies, the
synchronisation model between `CaseActor` and participant actors, and the
relationship to AppendOnlyLedger/LedgerFanout implementation phases.
**Load when**: implementing participant-side case replica handling, working on
`specs/participant-case-replica.yaml` (PCR) requirements, or designing the
`Announce(CaseLedgerEntry)` inbound handler.

**`participant-embargo-consent.md`**
Design decisions for per-participant embargo acceptance tracking: a 5-state
consent machine (`NO_EMBARGO`, `INVITED`, `SIGNATORY`, `LAPSED`, `DECLINED`),
embargo meta-protocol delivery to `DECLINED`/`LAPSED` participants, and the
`Accept(Invite(case))` → implicit consent rule. Records why `NO_EMBARGO` means
*absence of embargo* rather than pre-consent (ADR-0048), so `ACCEPT`/`DECLINE`
are valid directly from it, and the direct-assignment pitfall that silently
desyncs `ParticipantStatus.consent` from the emitted ledger snapshot.
**Load when**: implementing per-participant EM state tracking, working on the
embargo consent state machine in `vultron/core/states/`, writing any PEC state
change, or debugging `embargo_adherence` / `emConsentState` semantics.

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
Module conventions and known gaps: top-level modules, enum refactoring,
`vultron_types.py` split (TECHDEBT-14), `CVDRoles` design decision, BT
module boundary (`vultron/bt/` vs `vultron/core/behaviors/`), demo script
patterns (`demo_step` / `demo_check`), docstring/markdown compatibility,
bulk module-rename lessons, and known documentation gaps.
**Load when**: adding or moving modules, following established code
organization conventions, or orienting to the module boundary rules.

**`demo-scenario-authoring.md`**
How to write a multi-actor demo scenario without faking the protocol: puppeteer
actors through trigger endpoints rather than spoofing via inbox injection, never
carry one actor's mail to another's inbox, extract helpers before the second use,
keep console-script entry points callable with no arguments, and treat docker
service names as routing labels rather than actor identities.
**Load when**: writing or reviewing a demo scenario, adding a scenario helper, or
deciding whether a demo step is puppeteering or spoofing.

**`demo-ci-invariants.md`**
Design notes for the case-ledger invariant harness in demo CI: the
separate-job pattern (DEMOCI-04) that gives the invariant harness its own
independent pass/fail status even when the demo itself fails, the per-scenario
required event-type lists (DEMOMA-16), the table of required types per
scenario, and the spec-test sync rule.
**Load when**: modifying the demo CI workflow (`demo-integration.yml`),
adding or changing a scenario's expected event types, or debugging a silent
invariant harness failure in CI.

**`demo-ci-diagnostics.md`**
Diagnostic runbook for Demo Integration CI failures: the 3-layer diagnostic
model, a per-invariant diagnostic map, the local Docker run workflow, and how
to read the CI artifacts (including the per-actor ledger dumps).
**Load when**: triaging a red `Demo Integration` or `Invariant Harness` job,
or reproducing a scenario failure locally.

**`demo-ci-scenario-coverage.md`**
Coverage matrix mapping all 8 demo scenarios to the distinct protocol
`event_type` values each exercises, plus the minimum-PR-validation-set
analysis (DEMOCI-06): which 3 scenarios cover all 7 event types, rationale
for the minimum set, and workflow implementation notes.
**Load when**: evaluating which demo scenarios to include in the PR gate,
adding a new scenario and determining whether it changes the minimum set, or
auditing `full_suite_only` assignments in `demo-integration.yml`.

**`codebase-structure-fastapi-patterns.md`**
FastAPI and test infrastructure patterns: router test override pattern
(`_shared_dl`, `dependency_overrides`), circular import fix pattern
(`_helpers.py`), FastAPI `response_model` / `status_code` conventions,
health check and Docker health check design, Black/pyright config notes,
Python 3.14 compatibility deferral, surrogate-key routing collision
handling, and logger name verification.
**Load when**: writing FastAPI router tests, debugging import cycles,
implementing health check endpoints, or resolving surrogate-key routing
collisions.

**`triggerable-behaviors.md`**
Design notes for PRIORITY-30 trigger endpoints: trigger scope, endpoint
design sketch, actor independence, BT node classification, three-way report
validation, side effects of Emit FOO behaviors, placeholder behaviors,
SSVC-based prioritization, per-behavior design notes (embargo, CVE ID,
participants, notify others), invitation-ready case objects, and per-participant
embargo acceptance tracking.
**Load when**: implementing or modifying a trigger endpoint, designing the
request/response schema for a new trigger, or working on per-behavior trigger
logic.

**`triggerable-behaviors-resolved.md`**
Resolved trigger implementation design decisions and audit results: P30-1
(outbox diff strategy), P30-2 (report triggers procedural), P30-3 (case
triggers procedural), BT requirement for trigger use cases, general-purpose
vs demo-only trigger classification, trigger audit results, wrapper pattern,
sync-log-entry context field, and testing patterns.
**Load when**: verifying whether a trigger use case requires a BT, looking up
the resolved design rationale for the trigger architecture, or auditing trigger
classification (demo-only vs general-purpose).

**`architecture-ratchet-corpus.md`**
Design decisions and measurements for the shared corpus pattern in
`test/architecture/`: why a module-level source cache beats a session fixture
(timeout-window constraints), the prefilter approach, memory budget comparison,
xdist compatibility notes, and alternatives considered.
**Load when**: implementing or reviewing `test/architecture/_corpus.py`, adding
a new architecture ratchet test, auditing full-suite performance, or evaluating
xdist compatibility.

**`testing-pitfalls.md`**
Full write-ups for the pytest pitfalls that `test/AGENTS.md` only indexes:
reading a killed run, the two-tier timeout guardrail and why a tight ceiling
reads as flakiness, fixture/blackboard isolation, py_trees test patterns,
assertion-quality traps (vacuous asserts, "falls back to" tests, bare
`MagicMock`), and test layout rules for module splits.
**Load when**: writing or debugging tests, diagnosing an order-dependent or
apparently-flaky failure, or reviewing a test for vacuous assertions.

**`flaky-tests.md`**
Fast-lookup catalog of known flaky tests and CI jobs → tracking issue numbers.
Used by `pr-execute` as a cache before querying GitHub. GitHub is ground truth;
this file is a speed hint. Maintained by `pr-execute` (add) and `bugfix`/`build`
(remove on issue close).
**Load when**: triaging a pre-existing test failure in `pr-execute`, or auditing
the current set of known-flaky tests.

**`devcontainer-tooling.md`**
Environment-level pitfalls in this devcontainer: why every tool runs under
`uv run`, why `PYTHONPATH` must be cleared, the `UV_NO_SYNC=1` workaround for a
root-owned venv, the broken `gh` credential-helper path, and the hard-linked
`.agents/` and `.claude/` skill trees.
**Load when**: a tool fails to start, `git push` cannot authenticate, or you are
about to edit a skill file.

**`ci-workflow-authoring.md`**
Pitfalls when writing or reading GitHub Actions workflows: PyYAML resolving bare
`on:` to `True`, matrix booleans failing differently at job- vs. step-level
`if:`, `actionlint` and block-scalar indentation, single-quoted apostrophes, the
mandatory `notify-failure` wiring, and how to read a red job that never ran its
assertions.
**Load when**: adding or editing a `.github/workflows/` file, or diagnosing a CI
failure whose logs do not match the test it blames.

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
Extended multi-actor demo scenario sketches: FV (Finder + Vendor),
Three-Actor (Finder + Vendor + Coordinator), MultiParty (ownership transfer).
Describes what each scenario would demonstrate and open design questions.
**Load when**: designing new demo scripts or extending the existing demo suite
beyond the current FV scenario.

**`cvd-recipe-injects.md`**
Classification of all 21 CERT Guide to CVD problem-solving recipes as Vultron
scenario injects. Each recipe is mapped to RM/EM/CS protocol constructs and
assigned to a tier: A (implementable now), B (needs protocol/infra work), or
C (out of scope). Tier A recipes each have a Task issue under epic #1160;
Tier B recipes each have an Idea issue. Source: IDEA-1223.
**Load when**: designing new failure-path or abnormal-flow demo scenarios,
selecting which CVD recipes to implement as inject variations, or checking
whether a recipe has already been classified and tracked.

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

**`plan-history-management.md`** *(archived — see `plan/history/`)*
Superseded by `specs/history-management.yaml` and the `append-history` tool.
The IMPLEMENTATION_PLAN.md management rules it described are no longer relevant.

**`plan-organization.md`** *(archived — see `plan/history/`)*
Superseded — described the now-retired `TASK-FOO` naming scheme for
`plan/IMPLEMENTATION_PLAN.md`. All work is tracked as GitHub Issues.
See `notes/parallel-development.md` for the current model.

**`work-granularity.md`** *(archived — see `plan/history/`)*
Superseded — described the three-tier model (GitHub Issue → TASK-FOO →
checklist items). IMPLEMENTATION_PLAN.md has been removed; see
`specs/project-documentation.yaml` PD-09 for current guidance.

**`append-only-file-handling.md`** *(archived — see `plan/history/`)*
Superseded by `specs/history-management.yaml` and the `append-history` tool
(2026-04-28). The manual `cat >>` append procedure it describes is no longer
used.
**Load when**: investigating the pre-2026-04-28 history file procedure for
historical context only.

**`agentic-workflow.md`**
The four-skill agentic development pipeline: `ingest-idea`, `learn`,
`update-plan`, and `build`. Documents the inputs, outputs, and trigger
conditions for each skill, and the priority-interrupt loop that governs
execution order (design > learn > plan > build). Includes a Mermaid
flowchart and future BT automation notes.
**Load when**: understanding or evolving the agent skill pipeline, automating
the development loop, or deciding which skill to run next.

**`ownership-transfer.md`**
Implementation guidance for the ownership-transfer routing model (ADR-0053):
Offer and Accept MUST route through the CaseActor; correct flow for
`EmitOfferCaseOwnershipTransferNode`, `EmitAcceptCaseOwnershipTransferNode`,
`OfferCaseOwnershipTransferReceivedUseCase`, and the cascade wiring in
`ownership_transfer_tree.py`. Includes the demo workaround removal checklist.
**Load when**: implementing ownership-transfer routing fixes (CM-21-005,
CM-21-006, CM-21-007), auditing transfer routing in demos, or understanding
why the CaseActor must be the intermediary for ownership transfers.

**`coordination-agents.md`**
Design guidance for capability shapes — the five abstract interface contracts
(Sentinel, Evaluator, Retriever, Composer, Actuator) that answer Vultron
call-out points. Covers the two-surface integration model (trigger endpoints =
call-in; call-out points = call-out), the three-level taxonomy (shape /
capability / capability implementation), the trust/execution-authority axis,
composite capability design, and the fuzzer-node discovery methodology.
**Load when**: designing a new capability or call-out point integration,
working on the fuzzer-to-capability replacement roadmap, or explaining the
capability shape concept to new contributors.

**`git-workflow-pitfalls.md`**
The git and GitHub side of agentic development: rebase failures that are false
positives, `freshen-branch.sh` recovery, integration branches for related fix
PRs, `claim-issue.sh` preconditions, ADR number races, and the combined
verify-ACs-then-add-`Closes #N` rule.
**Load when**: a rebase or merge misbehaves, several related fix PRs are open at
once, or an issue looks implemented but is still open.

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

**`message-type-reference.md`**
Why the formal message set (shorthands partitioned by state machine) and the
AS2 wire vocabulary (`SEMANTIC_REGISTRY`) are different shapes, and how the
many-to-many mapping between them is documented. Contains the full collapse
inventory (CV/CF on `vf_state`, CP/CX/CA on `pxa_state`, EV/EJ/EC onto EP/ER/EA),
the expansion inventory (GI, EP, and the `Create`+`Add` split), the fault
trichotomy (not-understood / declined / needs-explanation), the cumulative
hash-chain acknowledgement model, the `docs/reference/messages/` page
architecture, and the MSM-03 post-mortem on `CV`/`CF`/`CD` being mapped to the
wrong object. Normative requirements:
`specs/message-semantics-mapping.yaml` MSM-04 through MSM-06. ADR: ADR-0083.
**Load when**: writing or reviewing anything that claims a protocol shorthand
maps to an AS2 wire form, working on `docs/reference/messages/`, adding a
`SEMANTIC_REGISTRY` entry, or reasoning about fault reporting and
acknowledgement. Source: IDEA-605.

**`spec-authoring-rules.md`**
Mechanical rules for authoring spec YAML: the exact enums `spec-lint` accepts
for `kind`, `priority`, and `rel_type`; keys silently dropped by `spec-dump`;
the protocol-coverage ratchet and its strict-`xfail` pattern; and the audit
passes required when retiring a name or splitting a compound requirement.
**Load when**: adding or editing any `specs/*.yaml` entry, or debugging a
spec-lint / `spec-dump` failure. Pair with `specs-vs-adrs.md` for *whether* the
requirement belongs in a spec at all.

**`notes-frontmatter.md`**
Design decisions for YAML frontmatter schema in `notes/*.md` files: required
fields (`title`, `status`), valid `status` values, `superseded_by` rule, schema
Pydantic model, loader, pre-commit hook, and migration checklist.
**Load when**: adding frontmatter to a new notes file, modifying the frontmatter
schema, or debugging `validate-notes-frontmatter` pre-commit failures.

**`spec-registry.md`** *(archived — `plan/history/2607/note/NOTES-spec-registry.md`)*
Implemented — `specs/*.md` fully migrated to YAML; `vultron/metadata/specs/` is in place.

**`demo-ci.md`** *(archived — `plan/history/2607/note/NOTES-demo-ci.md`)*
Implemented — `demo-integration.yml` workflow exists in `.github/workflows/`.

**`docs-build-workflow.md`** *(archived — `plan/history/2607/note/NOTES-docs-build-workflow.md`)*
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
