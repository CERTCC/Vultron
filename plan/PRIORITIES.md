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

## Priority 470 — Two-Actor Demo Redesign

Redesign the two-actor (Reporter + Vendor) CVD demo to implement a complete,
correct end-to-end CVD workflow: report submission, case creation with Case
Actor handoff, embargo bootstrap, fix lifecycle (VF → VFD → VFDPxa),
embargo teardown, and case closure.

See `notes/two-actor-demo.md` for the authoritative design; `specs/multi-actor-demo.yaml`
groups DEMOMA-06, DEMOMA-07, DEMOMA-08 for formal requirements.

- Epic: [#464](https://github.com/CERTCC/Vultron/issues/464)
- [#460](https://github.com/CERTCC/Vultron/issues/460) — Sub-issue A: Documentation and spec updates ✅
- [#461](https://github.com/CERTCC/Vultron/issues/461) — Sub-issue B: Core capabilities ✅
- [#462](https://github.com/CERTCC/Vultron/issues/462) — Sub-issue C: CASE_MANAGER role delegation protocol ✅
- [#469](https://github.com/CERTCC/Vultron/issues/469) — Case Actor spawning and CASE_MANAGER delegation automation ✅
- [#463](https://github.com/CERTCC/Vultron/issues/463) — Sub-issue D: Demo replacement ✅
- [#475](https://github.com/CERTCC/Vultron/issues/475) — Case Actor URN-based ID makes it unreachable via HTTP delivery ✅
- [#476](https://github.com/CERTCC/Vultron/issues/476) — Remove spec-violating workarounds from SvcAddParticipantStatusUseCase ✅
- [#483](https://github.com/CERTCC/Vultron/issues/483) — two\_actor\_demo.py: participant fetch, status check, and exception
  handling bugs ✅
- [#484](https://github.com/CERTCC/Vultron/issues/484) — Type narrowing: `_resolve_current_participant_state()` returns
  `tuple[Any, Any]` ✅
- [#467](https://github.com/CERTCC/Vultron/issues/467) — BT refactor: AddParticipantStatusToParticipant handler (also fixes RM
  transition validation regression) ✅
- [#489](https://github.com/CERTCC/Vultron/issues/489) — Extract shared helpers into vultron/demo/helpers/
- [#521](https://github.com/CERTCC/Vultron/issues/521) — PCR-07: Integration tests for case-replica bootstrap and late-joiner
  sequences (parent)
  - [#522](https://github.com/CERTCC/Vultron/issues/522) — PCR-07-006: bootstrap sequence (Create → Announce → replica)
  - [#523](https://github.com/CERTCC/Vultron/issues/523) — PCR-07-007: late-joiner sequence (Invite → Accept → Announce →
    replica)
- [#527](https://github.com/CERTCC/Vultron/issues/527) — Integration demo suite takes 17+ min in CI — polling helpers not
  patched ✅
- [#530](https://github.com/CERTCC/Vultron/issues/530) — Demo integration tests share a single DataLayer across actors —
  delivery path untested
- [#534](https://github.com/CERTCC/Vultron/issues/534) — Co-located actors in same process share module-level singletons
  (emitter, dispatcher, DataLayer)
- [#466](https://github.com/CERTCC/Vultron/issues/466) — Docs: two-actor-demo tutorial + technical reference (blocked by demo
  running end-to-end)
- [#471](https://github.com/CERTCC/Vultron/issues/471) — Tutorial: docs/tutorials/two-actor-demo.md
- [#472](https://github.com/CERTCC/Vultron/issues/472) — Technical reference: docs/reference/two-actor-demo-protocol.md

## Priority 476 — Bug Fixes and Demo Polish

Fix issues affecting demo execution and correctness.

- Epic: [#446](https://github.com/CERTCC/Vultron/issues/446)
- [#412](https://github.com/CERTCC/Vultron/issues/412) — mislabeled demo
  (docker-compose multi-vendor label mismatch)
- [#437](https://github.com/CERTCC/Vultron/issues/437) — Enforce spec vs.
  ADR delineation guidelines (MS-11)
- [#449](https://github.com/CERTCC/Vultron/issues/449) — Actor inbox
  endpoints return HTTP 404 during demo delivery ✅
- [#450](https://github.com/CERTCC/Vultron/issues/450) — Outbound activities
  missing required `to:` field (OX-08-001 violation) ✅
- [#451](https://github.com/CERTCC/Vultron/issues/451) — Invalid PEC state
  machine transition: `accept` trigger in NO_EMBARGO state ✅
- [#452](https://github.com/CERTCC/Vultron/issues/452) — Demo times out
  waiting for case to propagate to finder DataLayer ✅
- [#453](https://github.com/CERTCC/Vultron/issues/453) — Outbox processing
  aborts after too many `to:` field errors ✅
- [#454](https://github.com/CERTCC/Vultron/issues/454) — Coordinator actor
  unexpectedly persists the authoritative case ✅
- [#486](https://github.com/CERTCC/Vultron/issues/486) — HTTP-08-001
  violation: actors.py response\_model strips subclass fields
- [#487](https://github.com/CERTCC/Vultron/issues/487) — examples.py: add
  actor subtype example endpoints (VultronPerson, VultronOrganization, etc.)
- [#501](https://github.com/CERTCC/Vultron/issues/501) — Demo HTTP calls use
  `requests` which is not declared in `project.dependencies`
- [#517](https://github.com/CERTCC/Vultron/issues/517) — Migrate demo HTTP
  calls from `requests` to `httpx` (child of #501)
- [#518](https://github.com/CERTCC/Vultron/issues/518) — Document
  `vultron.adapters.driving.fastapi.main:app` as canonical deployment entry
  point

## Priority 480 — CBT-03: Pre-Bootstrap Queue Expiry

The pre-bootstrap inbox queue (`VultronPendingCaseInbox`) exists and can defer
activities when a case replica is not yet trusted, but has no bounded expiry.
This leaves two MUST-level requirements unimplemented: CBT-03-003 (drop and
warn on expiry) and CBT-03-004 (replay request to original report receiver).

See `specs/case-bootstrap-trust.yaml` CBT-03-001 through CBT-03-004,
CBT-05-003 and `notes/case-bootstrap-trust.md` §Out-of-Order Handling.

- [#500](https://github.com/CERTCC/Vultron/issues/500) — CBT-03: Implement
  bounded pre-bootstrap queue expiry and replay request

## Priority 485 — Architecture Hardening

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

## Priority 490 — Test File Refactoring

Refactor the largest test files to split by concern and consolidate duplicated
fixture code. The 10 largest files account for ~9,000 of 45,000+ test lines;
targeted splits improve navigation, reduce duplication, and make failures
easier to diagnose.

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

## Priority 495 — Production Source Refactoring

Split the largest production source files by concern to reduce merge conflicts,
improve navigability, and make tests more targeted. Complements P490 (test
file refactoring).

- [#504](https://github.com/CERTCC/Vultron/issues/504) — Several source files
  exceed 500 lines and mix multiple responsibilities
- [#514](https://github.com/CERTCC/Vultron/issues/514) — `vultron/core/behaviors/case/nodes.py`
  is the highest-churn source file at 1502+ lines
- [#516](https://github.com/CERTCC/Vultron/issues/516) — `vultron/core/use_cases/triggers/embargo.py`
  is a 792-line high-churn file with mixed responsibilities

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

## Priority 510 — Interactive Demo UI

Build an interactive web UI for stakeholder presentations that visualizes
Vultron protocol state in real time across all running actor containers and
lets a presenter (or viewer) make real protocol decisions at key branch
points. Replaces log-scrolling demos with a polished experience aimed at
non-technical audiences (government funders, industry practitioners).

- [#533](https://github.com/CERTCC/Vultron/issues/533) — Idea: Interactive
  ReactFlow Demo UI with CYOA scenarios for stakeholder presentations

## Priority 520 — Agent Guidance Freshness

The spec files and `AGENTS.md` change frequently as the codebase evolves,
causing agent sessions to start with stale context. This group tracks work
to make agent guidance more durable and easier to keep current. Note:
`PRIORITIES.md` is actively maintained; the concern is primarily with
`AGENTS.md` and spec files, which are harder to keep in sync.

- [#507](https://github.com/CERTCC/Vultron/issues/507) — Planning and
  specification files change so frequently that agent guidance goes stale
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

## Priority 3000: Miscellaneous tasks

- [#442](https://github.com/CERTCC/Vultron/issues/442) — Clean up orphaned
  BT-2.2/BT-2.3 placeholder references in PRIORITIES.md
- [#505](https://github.com/CERTCC/Vultron/issues/505) — Triage 15
  outstanding TODO/FIXME/XXX markers in production code

## Priority 95000: Documentation Enhancements — Crosswalks and Framework Integration

Low-priority documentation work to expand coverage of related frameworks
and scoring systems. These will be addressed as part of a broader
documentation refresh, after higher-priority code and architecture work is
complete.

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
