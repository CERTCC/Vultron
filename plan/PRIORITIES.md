# Priorities

## Important note about priority numbers

Priority numbers are ascending, so lower numbers are higher priority.
The scale is not linear, it's just intended to provide a rough ordering and
allow for space between to add new priorities in the future if needed. The
priority numbers themselves do not have any inherent meaning beyond their
relative order. Completed priorities should be archived via `uv run append-history priority`
(writes to `plan/history/YYMM/priority/`) and then removed from this file to keep
`plan/PRIORITIES.md` focused on pending and in-progress work.

Each priority group should have a corresponding GitHub Issue of type `Epic`
that tracks the overall work as child issues (which may in turn have their
own child issues, etc.) The list of child issues in GitHub is
authoritative regardless what is listed below, this file is a high-level
index and summary.

## Priority 480 — Epic #675: CBT-03: Pre-Bootstrap Queue Expiry

The pre-bootstrap inbox queue (`VultronPendingCaseInbox`) exists and can defer
activities when a case replica is not yet trusted, but has no bounded expiry.
This leaves two MUST-level requirements unimplemented: CBT-03-003 (drop and
warn on expiry) and CBT-03-004 (replay request to original report receiver).

See `specs/case-bootstrap-trust.yaml` CBT-03-001 through CBT-03-004,
CBT-05-003 and `notes/case-bootstrap-trust.md` §Out-of-Order Handling.

- Epic: [#675](https://github.com/CERTCC/Vultron/issues/675)
- [#500](https://github.com/CERTCC/Vultron/issues/500) — CBT-03: Implement
  bounded pre-bootstrap queue expiry and replay request
- [#663](https://github.com/CERTCC/Vultron/issues/663) —
  BroadcastStatusToPeersNode: participants re-broadcast to themselves
  (self-loop)

## Priority 485 — Epic #539: Architecture Hardening

Resolve structural fragilities in the core architecture: import boundary
violations, order-sensitive dispatch, fragile DataLayer scope conventions,
outbox polling, and oversized centralized dispatch tables.

- Epic: [#539](https://github.com/CERTCC/Vultron/issues/539)
- [#502](https://github.com/CERTCC/Vultron/issues/502) — Actor-scoped vs
  shared DataLayer scope boundaries are fragile and under-tested
- [#503](https://github.com/CERTCC/Vultron/issues/503) — Outbox drain loop
  uses fixed 1-second polling over all actor DataLayers
- [#506](https://github.com/CERTCC/Vultron/issues/506) — Architecture notes
  describe target layout as well as current structure, creating confusion
- [#508](https://github.com/CERTCC/Vultron/issues/508) — `semantic_registry.py`
  is a 783-line centralized dispatch table with tight coupling
- [#515](https://github.com/CERTCC/Vultron/issues/515) — `vultron/wire/as2/extractor.py`
  is order-sensitive and high-churn — pattern errors are easy to introduce
  silently
- [#519](https://github.com/CERTCC/Vultron/issues/519) — ARCH-01-001: Fix
  remaining core→wire import violations in report/nodes.py, received/actor.py,
  received/note.py
- [#535](https://github.com/CERTCC/Vultron/issues/535) — RFC: Replace
  `_mixins.py` 26-class mixin system with direct `@property` declarations on
  event subclasses
- [#537](https://github.com/CERTCC/Vultron/issues/537) — RFC: Add
  `InboxPipeline` to surface the `inbox_handler → dispatcher` seam as a
  testable boundary
- [#538](https://github.com/CERTCC/Vultron/issues/538) — RFC: Introduce
  `EmbargoLifecycle` service to consolidate fragmented embargo state management
- [#586](https://github.com/CERTCC/Vultron/issues/586) — Concern:
  `VultronActivity.object_` typed as `Any|None` causes dict round-trip bypass
- [#618](https://github.com/CERTCC/Vultron/issues/618) — Concern:
  Full-URI actor/case IDs embedded in URL path segments cause routing
  fragility
- [#622](https://github.com/CERTCC/Vultron/issues/622) — Concern:
  Trigger-side `execute()` methods contain inline state machine logic that
  should be in the BT
- [#632](https://github.com/CERTCC/Vultron/issues/632) — Concern:
  BT idiom audit: pervasive anti-patterns across use cases and BT nodes
- [#643](https://github.com/CERTCC/Vultron/issues/643) — SYNC-07-002/003:
  Integration tests for single-peer log replication cycle
- [#644](https://github.com/CERTCC/Vultron/issues/644) — TRACE-01-003:
  Update user-stories traceability matrix for newer spec topics
- [#649](https://github.com/CERTCC/Vultron/issues/649) — Demo HTTP helpers
  use `requests`, which is not a declared runtime dependency
- [#650](https://github.com/CERTCC/Vultron/issues/650) — Remote HTTP delivery
  and shared-inbox are architectural stubs with no implementation
- [#654](https://github.com/CERTCC/Vultron/issues/654) — Implement
  ActivityPub surrogate-key routing to replace Starlette path-converter
  workaround
- [#655](https://github.com/CERTCC/Vultron/issues/655) — Introduce
  ActorScopedDataLayer protocol to enforce DataLayer scope at type level
- [#656](https://github.com/CERTCC/Vultron/issues/656) — Add regression tests
  for DataLayer scope: get\_canonical\_actor\_dl and inbox\_handler dual-DL
  path
- [#689](https://github.com/CERTCC/Vultron/issues/689) — Case actor spawning
  architecture: vendor container should not own case actor
  (violates DEMAMA-01-001)
- [#690](https://github.com/CERTCC/Vultron/issues/690) — Fix case log
  observability: missing case-actor log, empty payloadSnapshot, replication
  gaps (violates CLP-02-003)

## Priority 490 — Epic #611: Test File Refactoring

Refactor the largest test files to split by concern and consolidate duplicated
fixture code. The 10 largest files account for ~9,000 of 45,000+ test lines;
targeted splits improve navigation, reduce duplication, and make failures
easier to diagnose.

- Epic: [#611](https://github.com/CERTCC/Vultron/issues/611)
- [#491](https://github.com/CERTCC/Vultron/issues/491) — Refactor largest
  test files: split by concern and consolidate fixtures (parent)
- [#492](https://github.com/CERTCC/Vultron/issues/492) — P1: Consolidate
  duplicated trigger-router fixtures into conftest.py
- [#493](https://github.com/CERTCC/Vultron/issues/493) — P2: Split
  test\_trigger\_embargo.py into per-operation files
- [#494](https://github.com/CERTCC/Vultron/issues/494) — P3: Split
  test\_sqlite\_backend.py by backend concern
- [#495](https://github.com/CERTCC/Vultron/issues/495) — P4: Split
  test\_report.py (received) by use-case type
- [#496](https://github.com/CERTCC/Vultron/issues/496) — P5: Split
  test\_vocab\_examples.py by domain area
- [#497](https://github.com/CERTCC/Vultron/issues/497) — P6: Split
  test\_outbox.py by functional area
- [#498](https://github.com/CERTCC/Vultron/issues/498) — P7 (optional):
  Light cleanup of test\_two\_actor\_demo.py

## Priority 495 — Epic #612: Production Source Refactoring

Split the largest production source files by concern to reduce merge conflicts,
improve navigability, and make tests more targeted. Complements P490 (test
file refactoring).

- Epic: [#612](https://github.com/CERTCC/Vultron/issues/612)
- [#504](https://github.com/CERTCC/Vultron/issues/504) — Several source files
  exceed 500 lines and mix multiple responsibilities
- [#514](https://github.com/CERTCC/Vultron/issues/514) — `vultron/core/behaviors/case/nodes.py`
  is the highest-churn source file at 1502+ lines
- [#516](https://github.com/CERTCC/Vultron/issues/516) — `vultron/core/use_cases/triggers/embargo.py`
  is a 792-line high-churn file with mixed responsibilities
- [#651](https://github.com/CERTCC/Vultron/issues/651) —
  `vultron/core/behaviors/report/nodes.py` is high-churn (31 commits/90d)
  alongside case BT nodes
- [#652](https://github.com/CERTCC/Vultron/issues/652) —
  `vultron/core/use_cases/triggers/case.py` is high-churn (31 commits/90d)
  and co-evolves with embargo logic
- [#653](https://github.com/CERTCC/Vultron/issues/653) —
  `vultron/adapters/driving/fastapi/outbox_handler.py` is high-churn (29
  commits/90d) as delivery model evolves

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

- [#427](https://github.com/CERTCC/Vultron/issues/427) — FUZZ-00:
  Re-implement fuzzer nodes from original simulator

## Priority 510 — Epic #676: Interactive Demo UI Frontend

Build the interactive demo UI frontend: an SSE-backed live display and a
polished ReactFlow web UI for stakeholder presentations. The UI visualizes
Vultron protocol state in real time across all running actor containers and
lets a presenter (or viewer) make real protocol decisions at key branch
points. Replaces log-scrolling demos with an experience aimed at
non-technical audiences (government funders, industry practitioners).

Note: backend correctness prerequisites — case actor spawning architecture
([#689](https://github.com/CERTCC/Vultron/issues/689)) and case log
observability fixes
([#690](https://github.com/CERTCC/Vultron/issues/690)) — have been moved
to P485.

- Epic: [#676](https://github.com/CERTCC/Vultron/issues/676)
- [#665](https://github.com/CERTCC/Vultron/issues/665) — Add SSE stream
  endpoint for live case log updates
- [#533](https://github.com/CERTCC/Vultron/issues/533) — Idea: Interactive
  ReactFlow Demo UI with CYOA scenarios for stakeholder presentations

## Priority 520 — Epic #613: Agent Guidance Freshness

The spec files and `AGENTS.md` change frequently as the codebase evolves,
causing agent sessions to start with stale context. This group tracks work
to make agent guidance more durable and easier to keep current. Note:
`PRIORITIES.md` is actively maintained; the concern is primarily with
`AGENTS.md` and spec files, which are harder to keep in sync.

- Epic: [#613](https://github.com/CERTCC/Vultron/issues/613)
- [#507](https://github.com/CERTCC/Vultron/issues/507) — Planning and
  specification files change so frequently that agent guidance goes stale ✅
- [#512](https://github.com/CERTCC/Vultron/issues/512) — `plan/`
  documentation is highly volatile and frequently causes stale context for
  agents
- [#513](https://github.com/CERTCC/Vultron/issues/513) — `AGENTS.md` and
  spec guidance files are high-churn, risking stale agent rules

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

- [#426](https://github.com/CERTCC/Vultron/issues/426) — AGENTIC-00:
  Agentic AI integration design and implementation

We will need to design the system in a way that allows for either of these
possibilities to be implemented in the future without requiring major refactoring.

## Priority 1500 — Epic #607: Documentation — Align with Diataxis Framework

Reorganize the documentation site to align with the
[Diataxis framework](https://diataxis.fr/): Tutorials, How-to Guides,
Explanation, and Reference. Adds audience-oriented entry points for CVD
practitioners, software developers, and contributors. Addresses content
misplacement, staleness, and gaps (especially the tutorial and developer
how-to sections).

- Epic: [#607](https://github.com/CERTCC/Vultron/issues/607)
- [#598](https://github.com/CERTCC/Vultron/issues/598) — Nav restructure:
  rename sections to diataxis terminology and add homepage persona entry points
- [#599](https://github.com/CERTCC/Vultron/issues/599) — Move misplaced
  Explanation content to Reference
- [#600](https://github.com/CERTCC/Vultron/issues/600) — Move
  worked\_example.md from Explanation to How-to Guides
- [#601](https://github.com/CERTCC/Vultron/issues/601) — Remove/review
  obsolete and aspirational content
- [#602](https://github.com/CERTCC/Vultron/issues/602) — Audit
  howto/activitypub/ for accuracy against current implementation
- [#603](https://github.com/CERTCC/Vultron/issues/603) — Tutorial: Submit a
  vulnerability report to a Vultron-speaking actor *(blocked by #602)*
- [#604](https://github.com/CERTCC/Vultron/issues/604) — How-to: Developer
  contributing guide
- [#605](https://github.com/CERTCC/Vultron/issues/605) — Reference:
  consolidated per-message-type reference pages *(blocked by #602)*
- [#606](https://github.com/CERTCC/Vultron/issues/606) — Reference: Protocol
  Quick Reference page *(blocked by #605, #599)*

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

- [#441](https://github.com/CERTCC/Vultron/issues/441) — Upgrade
  external-decision fuzzer nodes to full implementations

## Priority 3000 — Epic #614: Miscellaneous Tasks

- Epic: [#614](https://github.com/CERTCC/Vultron/issues/614)
- [#442](https://github.com/CERTCC/Vultron/issues/442) — Clean up orphaned
  BT-2.2/BT-2.3 placeholder references in PRIORITIES.md ✅
- [#505](https://github.com/CERTCC/Vultron/issues/505) — Triage 15
  outstanding TODO/FIXME/XXX markers in production code
- [#627](https://github.com/CERTCC/Vultron/issues/627) — Use
  `SqliteDataLayer` as a context manager in yield-based test fixtures

## Priority 95000 — Epic #615: Documentation Enhancements — Crosswalks and Framework Integration

Low-priority documentation work to expand coverage of related frameworks
and scoring systems. These will be addressed as part of a broader
documentation refresh, after higher-priority code and architecture work is
complete.

- Epic: [#615](https://github.com/CERTCC/Vultron/issues/615)
- [#5](https://github.com/CERTCC/Vultron/issues/5) — Integrate FIRST services frameworks
- [#6](https://github.com/CERTCC/Vultron/issues/6) — Add CVSSv4 crosswalk

## Priority 97000: MkDocs Replacement

Migrate documentation build tooling from MkDocs 1.x to Zensical (MkDocs 2.0
compatibility). MkDocs 2.0 is a ground-up rewrite that is incompatible with
the current plugin ecosystem and configuration format.

- [#294](https://github.com/CERTCC/Vultron/issues/294) — Plan migration to Zensical for MkDocs 2.0 compatibility

## Priority 99999 — Remaining Requirements and Documentation Updates

The project is currently in prototype development mode, therefore requirements
that are marked as `PROD_ONLY` are temporarily a lower priority than other
requirements. See `specs/prototype-shortcuts.yaml` for the prototype-stage
deferral policy.

- Epic: [#447](https://github.com/CERTCC/Vultron/issues/447)
- [#422](https://github.com/CERTCC/Vultron/issues/422) — USE-CASE-01:
  CloseCaseUseCase wire-type construction
- [#423](https://github.com/CERTCC/Vultron/issues/423) — USE-CASE-02:
  UseCase Protocol generic enforcement
- [#424](https://github.com/CERTCC/Vultron/issues/424) — EP-02/EP-03:
  EmbargoPolicy API + compatibility evaluation (PROD_ONLY)
- [#425](https://github.com/CERTCC/Vultron/issues/425) — AR-04/05/06:
  Job tracking, pagination, bulk ops (PROD_ONLY)
- [#509](https://github.com/CERTCC/Vultron/issues/509) — No authentication
  or message-signing in HTTP inbox/outbox delivery paths (PROD_ONLY)
- [#510](https://github.com/CERTCC/Vultron/issues/510) — Secret handling
  relies on plain environment variables with no rotation or secrets manager
  (PROD_ONLY)
- [#511](https://github.com/CERTCC/Vultron/issues/511) — SQLite is the only
  persistence backend; multi-writer and high-volume deployments unsupported
  (PROD_ONLY)
- [#526](https://github.com/CERTCC/Vultron/issues/526) — Idea: Scheduled
  GitHub Action for automated monthly/quarterly project reports
