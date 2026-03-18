# Vultron API v2 Implementation Plan

**Last Updated**: 2026-03-18 (VCR-019c: enum/state consolidation study complete)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Completed phase history is in `plan/IMPLEMENTATION_HISTORY.md`.

### Current Status Summary

**Test suite**: 981 passing, 5581 subtests, 5 warnings (2026-03-18, after VCR-006)

**All 38 handlers implemented** (including `unknown`) — see `IMPLEMENTATION_HISTORY.md`.
**Trigger endpoints**: all 9 complete (P30-1–P30-6). **Demo scripts**: 12 scripts,
all dockerized in `docker-compose.yml`. **P75 phase**: ALL COMPLETE (P75-1 through
P75-5). `api/v1` removed; vocabulary examples consolidated into
`api/v2/routers/examples.py` (ADR-0011). All 38 handler use cases and 9 trigger
use cases are class-based. CLI (`vultron/adapters/driving/cli.py`) and MCP
(`vultron/adapters/driving/mcp_server.py`) driving adapters implemented.
**TECHDEBT-16 complete**: `VultronObject` base class defined in
`vultron/core/models/base.py`; all 12 domain object models inherit from it.

**Active phase**: **PRIORITY-80** — technical debt cleanup and full hexagonal
architecture realization. TECHDEBT-16 through TECHDEBT-28 are complete; VCR-A
batch (7/8 tasks) complete. VCR-030 blocked on
removing `vultron.sim` callers in `vultron/bt/`. VCR-B batch complete.
VCR-019c study complete — implementation guidance in `plan/IMPLEMENTATION_NOTES.md`.

---

## Gap Analysis (2026-03-16, refresh #39)

### ✅ Previously completed (see `plan/IMPLEMENTATION_HISTORY.md`)

BUGFIX-1, REFACTOR-1, DEMO-3, DEMO-4, SPEC-COMPLIANCE-1, SPEC-COMPLIANCE-2,
SC-3.1, SC-PRE-1, TECHDEBT-1, TECHDEBT-5, TECHDEBT-6, TECHDEBT-10, TECHDEBT-11, P30-1,
P30-2, P30-3, P30-4, P30-5, P30-6, P50-0, ARCH-1.1, ARCH-1.2, ARCH-1.3,
ARCH-1.4, ARCH-CLEANUP-1, ARCH-CLEANUP-2, ARCH-CLEANUP-3, ARCH-ADR-9, P60-1,
P60-2, P60-3, TECHDEBT-3, TECHDEBT-7, TECHDEBT-8, TECHDEBT-9, TECHDEBT-10,
TECHDEBT-11, TECHDEBT-12, SC-PRE-2, SC-3.2, SC-3.3,
P65-1, P65-2, P65-3, P65-4, P65-5, P65-6a, P65-6b, P65-7,
ARCH-DOCS-1, TECHDEBT-13a, TECHDEBT-13b, TECHDEBT-13c, TECHDEBT-14,
P70-2, P70-3, P70-4, P70-5,
P75-1, P75-2, P75-2a, P75-2b, P75-2c, P75-3, P75-4-pre,
TECHDEBT-15, TECHDEBT-21, TECHDEBT-22, TECHDEBT-24, TECHDEBT-27, P75-5.

### ❌ Outbox delivery not implemented (lower priority)

`actor_io.py` stub logs placeholder messages (OX-03-001, OX-04-001, OX-04-002).
`core/ports/emitter.py` Protocol stub not yet created (see `notes/architecture-ports-and-adapters.md`
"Dispatch vs Emit Terminology"). Needed before OUTBOX-1 implementation.

### ✅ Triggerable behaviors fully implemented (PRIORITY 30 — COMPLETE)

All 9 trigger endpoints in split router files. P30-1 through P30-6 complete.

### ✅ Hexagonal architecture violations remediated (PRIORITIES 65/75 — ALL COMPLETE)

All P65 and P75 architecture tasks complete. All violations V-01 through V-24
and TECHDEBT-13a–c are fully resolved. `notes/architecture-review.md` is
up to date.

### ✅ Package relocation Phase 1 complete (PRIORITY 60 — COMPLETE)

- `vultron/as_vocab/` → `vultron/wire/as2/vocab/` (P60-1 ✅)
- `vultron/behaviors/` → `vultron/core/behaviors/` (P60-2 ✅)
- `vultron/adapters/` package stub created (P60-3 ✅)

### ✅ DataLayer refactor into ports and adapters (PRIORITY 70 — COMPLETE)

P70-2 through P70-5 all complete. All callers import `DataLayer` from
`vultron.core.ports.datalayer`, `TinyDbDataLayer`/`get_datalayer` from
`vultron.adapters.driven.datalayer_tinydb`, and `Record`/`object_to_record`
from `vultron.adapters.driven.db_record`.

### ✅ Handler and trigger-service logic in core/use_cases/ (PRIORITY 75 — P75-1/2/3 COMPLETE)

All 38 handler use cases and 9 trigger-service use cases now live in
`vultron/core/use_cases/`. The handler adapter layer is reduced to
`handlers/_shim.py`. The dispatcher is modelled as a formal driving port
(`core/ports/dispatcher.py`) backed by `core/dispatcher.py`. The routing
table (`USE_CASE_MAP`) lives in `core/use_cases/use_case_map.py`. Pattern
objects in `extractor.py` use the `Pattern` suffix. P75-4 and P75-5 complete.

### ✅ UseCase interface standardized (P75-4-pre — complete)

`UseCase[Req, Res]` Protocol defined in `vultron/core/ports/use_case.py`.
`UnknownUseCase` in `vultron/core/use_cases/unknown.py` is the reference
implementation; the old callable wrapper delegates to it for backward compat.
P75-4 MUST refactor every use case it touches to the class interface.

### ✅ api/v1 removed (P75-5 — COMPLETE)

`vultron/api/v1/` removed. Vocabulary-example endpoints migrated to
`api/v2/routers/examples.py`. Decision recorded in ADR-0011.

### ❌ Actor independence not implemented (PRIORITY 100)

All actors share a singleton `TinyDbDataLayer` instance. PRIORITY 100 requires
per-actor isolated state. Options documented in `notes/domain-model-separation.md`
(Option B: TinyDB namespace prefix; MongoDB community edition for production).
Blocked by PRIORITY-70 (complete ✅).

### ❌ CaseActor broadcast not implemented (PRIORITY 200)

CM-06-001 requires CaseActor to notify all case participants on case state update.
Blocked by OUTBOX-1.

### ✅ SPEC-COMPLIANCE-3 complete (SC-PRE-2, SC-3.2, SC-3.3 all done)

`SC-PRE-2`, `SC-3.2`, and `SC-3.3` are all complete. The `update_case` guard
checks participant embargo acceptance and logs a WARNING (CM-10-004); full
enforcement deferred to PRIORITY-200.

### ❌ Flaky test not yet fixed (TECHDEBT-15 — new gap)

`test_remove_embargo` in `test/wire/as2/vocab/test_vocab_examples.py:819`
occasionally fails due to py_trees blackboard global state shared across tests.
`specs/testability.md` TB-06-006 mandates all tests be deterministic. Fix:
add `autouse` fixture in `test/wire/as2/vocab/conftest.py` to clear the
blackboard before each test.

### ✅ DRY core domain models (TECHDEBT-16 — complete)

`VultronObject` base class added in `vultron/core/models/base.py`. All 12 domain
object model classes now inherit from `VultronObject` (which provides `as_id`,
`as_type`, `name`). Repeated field definitions removed. 48 new tests added in
`test/core/models/test_base.py`. 961 tests pass.

### ❌ `docker/README.md` out of date (DOCS-1 — new gap)

`docker/README.md` lists individual per-demo services that no longer exist
in `docker-compose.yml` (now consolidated into a unified `demo` service).
Captured in `notes/codebase-structure.md`. Needs update to describe `api-dev`,
`demo`, `test`, `docs`, and `vultrabot-demo` services.

### ❌ Broken inline code examples in `docs/` (DOCS-2 — new gap)

`docs/reference/code/as_vocab/*.md` reference old `vultron.as_vocab.*` module
paths that moved to `vultron.wire.as2.vocab.*` during P60-1. Running
`mkdocs build` surfaces these errors. Captured in `notes/codebase-structure.md`.

### ❌ Multi-actor demos not yet started (PRIORITY 300)

Blocked by PRIORITY-100 and PRIORITY-200.

---

## Prioritized Task List

### Phase PRIORITY-30 — Triggerable Behaviors (COMPLETE ✅)

All P30 tasks (P30-1 through P30-6) complete. All 9 trigger endpoints implemented.
See `plan/IMPLEMENTATION_HISTORY.md` for details.

---

### Phase PRIORITY-50/60/65 — Hexagonal Architecture (ALL COMPLETE ✅)

P50-0, ARCH-1.1–1.4, ARCH-CLEANUP-1/2/3, P60-1/2/3, P65-1–7 all complete.
V-01 through V-24 resolved. See `plan/IMPLEMENTATION_HISTORY.md` for details.

---

### Phase SPEC-COMPLIANCE-3 — Embargo Acceptance Tracking (COMPLETE ✅)

SC-PRE-2, SC-3.2, SC-3.3 all complete. See `plan/IMPLEMENTATION_HISTORY.md`.

---

### Technical Debt (housekeeping) — batches 1–14 complete ✅

TECHDEBT-3, TECHDEBT-7, TECHDEBT-8, TECHDEBT-9, TECHDEBT-10, TECHDEBT-11,
TECHDEBT-12, TECHDEBT-13a/b/c, TECHDEBT-14 all done. TECHDEBT-4 superseded
by P70-2. See `plan/IMPLEMENTATION_HISTORY.md`.

---

### ARCH-DOCS-1 — Update architecture-review.md violation status markers (COMPLETE ✅)

See `plan/IMPLEMENTATION_HISTORY.md`.

---

### Phase PRIORITY-70 — DataLayer Refactor into Ports and Adapters (COMPLETE ✅)

P70-2 through P70-5 all complete. See `plan/IMPLEMENTATION_HISTORY.md`.

---

### Phase PRIORITY-75 — api/v2 Business Logic → core/use_cases/ (ALL COMPLETE ✅)

P75-1, P75-2, P75-2a, P75-2b, P75-2c, P75-3 all complete.
See `plan/IMPLEMENTATION_HISTORY.md` for details.

#### Remaining P75 tasks

- [x] **P75-4-pre**: Standardize use-case interface: `UseCase[Req, Res]` Protocol
  defined in `vultron/core/ports/use_case.py`. `UnknownUseCase` is the reference
  implementation. Old callable wrapper kept for backward compat. **COMPLETE.**

- [x] **P75-4**: All 38 handler use cases and 9 trigger use cases converted to
  `XxxUseCase` / `SvcXxxUseCase` classes. Dispatcher updated to call
  `use_case_class(dl).execute(event)`. Trigger service adapter shims updated.
  CLI adapter (`vultron/adapters/driving/cli.py`) implemented with `click`.
  MCP adapter (`vultron/adapters/driving/mcp_server.py`) implemented with 9 tool
  functions + `MCP_TOOLS` list. **COMPLETE.**

- [x] **P75-5**: Removed `vultron/api/v1/`. Vocabulary-example endpoints
  (reports, cases, participants, embargoes) migrated to
  `api/v2/routers/examples.py`. Decision recorded in `docs/adr/0011-remove-api-v1.md`.
  **COMPLETE.**

---

### Phase PRIORITY-80 — Technical Debt and Architecture Cleanup

**Reference**: `plan/PRIORITIES.md` PRIORITY 80

This phase addresses accumulated technical debt and
ensures the hexagonal architecture is fully realized before moving to PRIORITY-100.

**Recommended execution order** (batching guidance):

- **Batch 80a** (dead code, quick wins — batch TECHDEBT-17 + 18 + 20 together):
  TECHDEBT-17, TECHDEBT-18, TECHDEBT-20 are independent dead-code deletions with
  no behaviour change. Run one commit for all three.
- **Batch 80b** (architecture violations — TECHDEBT-19 + 24 share context):
  Both remove wrong-layer imports from core. TECHDEBT-24 (`VulnerabilityCase`
  and `ParticipantStatus` imports from wire layer in `triggers/_helpers.py` and
  `case.py`) may be partially resolved by TECHDEBT-19 (moving `rehydrate` /
  status helpers out of `api.v2`). Attempt together.
- **Batch 80c** (naming + Protocol base — TECHDEBT-21 then 22):
  TECHDEBT-21 must complete before TECHDEBT-22; both can ship in one PR.
- **Batch 80d** (error handling — TECHDEBT-27 + 28 + related deferred items):
  TECHDEBT-27 (error handling standardization) and TECHDEBT-28
  (idempotent-create helper) are newly un-deferred now that P75-4 is done.
  Group with the stub `try/except` cleanup from the Deferred section.
- **Batch 80e** (DRY / cleanup — low-risk, low-priority):
  TECHDEBT-16, TECHDEBT-23, TECHDEBT-25, TECHDEBT-26 in any order.

---

### TECHDEBT-15 — Fix flaky `test_remove_embargo` test

**Priority**: High (spec TB-06-006 — all tests MUST be deterministic)

- [x] **TECHDEBT-15**: Fix `test_remove_embargo` in
  `test/wire/as2/vocab/test_vocab_examples.py:819`. The test fails
  non-deterministically due to py_trees blackboard global state leaking between
  tests. Fix: add an `autouse` fixture in
  `test/wire/as2/vocab/conftest.py` that clears
  `py_trees.blackboard.Blackboard.storage` before and after each test (see
  AGENTS.md "py_trees Blackboard Global State" section). Done when
  `test_remove_embargo` passes reliably in the full test suite across multiple
  runs and no other tests in the file are affected.

---

### TECHDEBT-16 — DRY core domain models (VultronObject base class)

**Priority**: Low (organizational, `notes/domain-model-separation.md`)

- [x] **TECHDEBT-16**: Add a `VultronObject` base class in `vultron/core/models/`
  capturing common fields shared by all domain objects (e.g., `id`, `name`,
  `created_at`, `updated_at`). Have `VultronEvent` and other domain model classes
  inherit from `VultronObject` rather than directly from `BaseModel`. Mirrors
  the wire-layer class hierarchy at the domain level. Done when the base class
  is defined, all domain model classes inherit from it, repeated field
  definitions are removed, and tests pass.

---

### TECHDEBT-17 — Delete dead functions in `core/use_cases/embargo.py`

**Priority**: High (dead code, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 1

- [x] **TECHDEBT-17**: Delete bare function implementations (`create_embargo_event`,
  `add_embargo_event_to_case`, etc.) from `vultron/core/use_cases/embargo.py`
  starting at the line after `RejectInviteToEmbargoOnCaseUseCase`. These are
  pre-refactor function stubs that duplicate the class-based implementations above
  them and are not referenced anywhere. Done when all dead bare-function definitions
  are removed, no import or call sites reference them, and the test suite passes.

---

### TECHDEBT-18 — Delete dead duplicate block in `triggers/report.py`

**Priority**: High (dead code, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 2

- [x] **TECHDEBT-18**: Delete the duplicate import block and second definition of
  `_resolve_offer_and_report` from `vultron/core/use_cases/triggers/report.py`
  (the block starting with a bare `import logging` after `SvcCloseReportUseCase`).
  Done when no duplicate imports or function definitions remain, and the test suite
  passes.

---

### TECHDEBT-19 — Remove `api.v2.*` imports from `triggers/report.py`

**Priority**: High (ARCH-05 / CS-05-001 violation, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 3

- [x] **TECHDEBT-19**: Moved `rehydrate` to `vultron/wire/as2/rehydration.py`
  (with `dl: DataLayer | None = None` parameter to eliminate the adapter-layer
  `get_datalayer()` fallback for callers that already hold a DataLayer). Deleted
  `vultron/api/v2/data/rehydration.py`. Updated all callers
  (`triggers/report.py`, `inbox_handler.py`, `cli.py`, `routers/datalayer.py`,
  and all tests) to import from `vultron.wire.as2.rehydration` directly.
  Changed `triggers/report.py` status imports from `api.v2.data.status` to
  `vultron.core.models.status` (which was already the authoritative location).

---

### TECHDEBT-20 — Delete dead import block in `triggers/embargo.py`

**Priority**: High (dead code, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 10

- [x] **TECHDEBT-20**: Delete the duplicate import block from
  `vultron/core/use_cases/triggers/embargo.py` that starts with a bare
  `import logging` after `SvcTerminateEmbargoUseCase` and ends with a
  duplicate `logger = logging.getLogger(__name__)`. Done when all duplicated
  imports and logger assignments are removed and the test suite passes.

---

### TECHDEBT-21 — Rename handler use cases with `Received` suffix

**Priority**: High (naming convention, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 11;
`specs/code-style.md` CS-12-002

- [x] **TECHDEBT-21**: Renamed all 38 handler use cases in the 7 top-level
  modules (`actor.py`, `case.py`, `case_participant.py`, `embargo.py`,
  `note.py`, `report.py`, `status.py`) to append the `Received` suffix
  (e.g., `CreateReportUseCase` → `CreateReportReceivedUseCase`). Updated
  `USE_CASE_MAP` in `core/use_cases/use_case_map.py` and the shim layer in
  `vultron/api/v2/backend/handlers/__init__.py`. Pure mechanical rename, no
  behaviour change. 893 tests pass.

---

### TECHDEBT-22 — Declare `UseCase[Req, Res]` Protocol base on every use case class

**Priority**: Medium (type safety, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 12

- [x] **TECHDEBT-22**: Add `UseCase[RequestType, ResponseType]` as the explicit
  Protocol base for every use case class in `core/use_cases/`. Handler use cases
  return `None`; trigger use cases return `dict`. All 47 use case classes updated
  across 11 files. 893 tests pass.

---

### TECHDEBT-23 — Extract `TriggerRequest` base class in `triggers/requests.py`

**Priority**: Low (DRY, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 13

- [x] **TECHDEBT-23**: Added `TriggerRequest` base class in
  `vultron/core/use_cases/triggers/requests.py` with `model_config = ConfigDict(extra="ignore")`
  and `actor_id: NonEmptyString`. All 9 concrete trigger request models
  subclass `TriggerRequest` with the duplicated `model_config` and
  `actor_id` fields removed from each. 893 tests pass.

---

### TECHDEBT-24 — Remove wire-layer imports from core use cases

**Files**: `core/use_cases/case.py` and `triggers/_helpers.py`

**Priority**: Medium (ARCH-06 violation, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 4

- [x] **TECHDEBT-24** (partial — `triggers/_helpers.py` done): Removed
  `VulnerabilityCase` and `ParticipantStatus` imports from
  `triggers/_helpers.py`. `resolve_case` now returns `CaseModel`; a new
  `append_rm_state(rm_state, actor, context)` method was added to both
  `CaseParticipant` (wire) and `ParticipantModel` (Protocol), eliminating
  the need to instantiate `ParticipantStatus` in the helper.
- [x] **TECHDEBT-24** (remaining — `case.py`): Resolved using option (a):
  `VultronCase.case_statuses` now initialises with `[VultronCaseStatus()]` via a
  `default_factory` lambda, matching `VulnerabilityCase.init_case_status()`. The
  lazy import of `VulnerabilityCase` in `CreateCaseReceivedUseCase.execute` was
  removed; `request.case` (already a `VultronCase`) is passed directly to
  `create_create_case_tree`. `case.py` has no imports from `vultron.wire.*` and
  893 tests pass.

---

### TECHDEBT-25 — Extract `_as_id()` helper to eliminate repeated pattern

**Priority**: Low (DRY, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 5

- [x] **TECHDEBT-25**: Created `vultron/core/use_cases/_helpers.py` with
  `_as_id(obj) -> str | None` helper. Replaced all ~15 call sites in
  `case.py`, `actor.py`, `embargo.py`, `case_participant.py`, `note.py`,
  and `status.py`. 893 tests pass.

---

### TECHDEBT-26 — Replace `OptionalNonEmptyString` alias with `NonEmptyString | None`

**Priority**: Low (cleanup, raised in `plan/IDEAS.md`)

**Source**: `plan/IDEAS.md` "Most strings in Pydantic objects should be NonEmptyStrings";
`specs/code-style.md` CS-08-002

- [x] **TECHDEBT-26**: Removed `OptionalNonEmptyString` type alias from
  `vultron/wire/as2/vocab/base/types.py` and `vultron/core/models/events/base.py`.
  Replaced all usages with the inline form `NonEmptyString | None` across
  `base.py`, `case_reference.py`, `embargo_policy.py`, `vulnerability_record.py`,
  `case_participant.py`, and `case_status.py`. Removed re-export from
  `core/models/events/__init__.py`. Updated `specs/code-style.md` CS-08-002.
  893 tests pass.

---

### TECHDEBT-27 — Standardize error handling in use cases

**Priority**: Medium (un-deferred now that P75-4 is complete)

**Source**: `plan/IMPLEMENTATION_NOTES.md` code-review item 6 (deferred); promoted
from Deferred section after P75-4 completion.

- [x] **TECHDEBT-27**: Remove silent `except Exception` swallowers from use cases;
  let domain exceptions propagate and be caught at the dispatcher boundary. Also
  remove the meaningless `try/except Exception` wrappers from stub-only use cases
  (`RejectSuggestActorToCaseUseCase`, `RejectCaseOwnershipTransferUseCase`,
  `RejectInviteActorToCaseUseCase`, `RejectInviteToEmbargoOnCaseUseCase`,
  `AnnounceEmbargoEventToCaseUseCase`) that wrap a `logger.info()` call which
  can never raise. Ensure the dispatcher logs unexpected exceptions at ERROR level
  with full context before re-raising. Done when no use case contains a bare
  `except Exception` swallower, all domain exceptions propagate to the dispatcher,
  and the test suite passes.

---

### TECHDEBT-28 — Extract idempotent-create helper

**Priority**: Low (un-deferred now that P75-4 is complete)

**Source**: `plan/IMPLEMENTATION_NOTES.md` code-review item 14 (deferred); promoted
from Deferred section after P75-4 completion.

- [x] **TECHDEBT-28**: Added `_idempotent_create(dl, type_key, id_key, obj, label,
  activity_id)` module-level function to `vultron/core/use_cases/_helpers.py`
  (alongside `_as_id()`). Replaced the idempotency guard pattern across
  `CreateEmbargoEventReceivedUseCase`, `CreateNoteReceivedUseCase`,
  `CreateCaseParticipantReceivedUseCase`, `CreateCaseStatusReceivedUseCase`,
  `CreateParticipantStatusReceivedUseCase`, `SuggestActorToCaseReceivedUseCase`,
  `AcceptSuggestActorToCaseReceivedUseCase`, `OfferCaseOwnershipTransferReceivedUseCase`,
  `InviteActorToCaseReceivedUseCase`, and `InviteToEmbargoOnCaseReceivedUseCase`.
  893 tests pass. **Batched with TECHDEBT-25**.

---

### DOCS-1 — Update `docker/README.md`

**Priority**: Medium (docs correctness, `notes/codebase-structure.md`)

- [ ] **DOCS-1**: Update `docker/README.md` to accurately describe the current
  `docker-compose.yml` services: `api-dev` (API server), `demo` (unified demo
  runner for all demo scripts), `test` (pytest), `docs` (MkDocs), and
  `vultrabot-demo`. Remove references to individual per-demo service containers
  (e.g., `receive-report-demo`, `initialize-case-demo`, etc.) that have been
  consolidated into the `demo` service. Done when the README accurately reflects
  the current services and how to run them.

---

### DOCS-2 — Fix broken inline code examples in `docs/`

**Priority**: Medium (docs correctness, `notes/codebase-structure.md`)

- [ ] **DOCS-2**: Update `docs/reference/code/as_vocab/*.md` files that reference
  old `vultron.as_vocab.*` module paths (moved to `vultron.wire.as2.vocab.*`
  during P60-1). Run `mkdocs build` to surface all broken references, then update
  the affected code blocks and `:::: module.path` autodoc directives to use the
  new paths. Done when `mkdocs build` succeeds without module-not-found errors
  in `docs/reference/code/as_vocab/`.

---

### Phase BT-2.2/2.3 — Optional BT Refactors (low priority)

- [ ] **BT-2.2**: Refactor `close_report` handler to use BT tree
  (reference: `vultron/bt/report_management/_behaviors/close_report.py`)
- [ ] **BT-2.3**: Refactor `invalidate_report` handler to use BT tree
  (reference: `_InvalidateReport` subtree in `validate_report.py`)

---

### Phase VCR-0317 — Architecture Consolidation (2026-03-17 Code Review)

**Source**: `plan/IDEAS.md` VCR-0317 code review items (March 17, 2026).
Organized into batches by concern. These tasks are part of PRIORITY-80.

#### Batch VCR-A — Dead code and shim removal

All items in this batch are pure deletions with no behaviour change.
Batch together where possible.

- [x] **VCR-001**: Delete `vultron/adapters/driven/dns_resolver.py` stub —
  DNS resolution is an adapter-level detail with no current callers; the file
  is a placeholder with no implementation.
- [x] **VCR-006**: Delete `vultron/api/v2/backend/handler_map.py` — this is a
  shim that re-exports `USE_CASE_MAP` as `SEMANTICS_HANDLERS`. Verified no
  callers remained (only `test/test_semantic_handler_map.py`, updated to import
  `USE_CASE_MAP` directly). 981 tests pass.
- [x] **VCR-015a**: Delete `vultron/api/v2/data/status.py` — this is a shim
  re-exporting status helpers. Update callers to import directly from the
  canonical source (`vultron.core.models.status`).
- [x] **VCR-015b**: Delete `vultron/api/v2/data/types.py` — confirmed no active
  callers; deleted.
- [x] **VCR-024**: Delete `vultron/core/ports/dns_resolver.py` — DNS resolution
  is an adapter concern; no port interface is needed. Verified no callers, then
  deleted.
- [ ] **VCR-030**: Delete `vultron/sim/` module — blocked: `vultron/bt/states.py`,
  `vultron/bt/messaging/outbound/behaviors.py`, `vultron/bt/messaging/inbound/fuzzer.py`,
  and `vultron/bt/report_management/_behaviors/report_to_others.py` all import
  `vultron.sim.messages.Message`. Update these callers before deleting.
  (auto-added prerequisite: relocate or replace `vultron.sim.messages.Message`)
- [x] **VCR-031**: Delete `vultron/behavior_dispatcher.py` — updated
  `test/test_behavior_dispatcher.py` to import from canonical locations
  (`vultron.core.dispatcher`, `vultron.core.ports.dispatcher`), then deleted shim.
- [x] **VCR-032**: Merged `vultron/dispatcher_errors.py` into `vultron/errors.py`.
  Moved `VultronApiHandlerNotFoundError` to `vultron/errors.py`. Updated
  `vultron/core/dispatcher.py` and `vultron/api/v2/errors.py` to import from
  `vultron.errors`. Deleted `vultron/dispatcher_errors.py`.

#### Batch VCR-B — API v2 → adapters consolidation

These tasks consolidate `vultron/api/v2/` into `vultron/adapters/driving/fastapi/`.
They are larger structural changes; plan as a single coordinated PR.

- [x] **VCR-003/004/007/008/009/017/018**: Created `vultron/adapters/driving/fastapi/`
  subpackage. Moved:

  - `vultron/api/v2/routers/` → `vultron/adapters/driving/fastapi/routers/`
  - `vultron/api/v2/app.py` + `vultron/api/main.py` → `vultron/adapters/driving/fastapi/app.py`
    and `vultron/adapters/driving/fastapi/main.py`
  - `vultron/api/v2/backend/inbox_handler.py` → `vultron/adapters/driving/fastapi/inbox_handler.py`
    (replaced `vultron/adapters/driving/http_inbox.py` stub)
  - `vultron/api/v2/backend/outbox_handler.py` → `vultron/adapters/driving/fastapi/outbox_handler.py`
  - `vultron/api/v2/errors.py` → `vultron/adapters/driving/fastapi/errors.py`
  - `vultron/api/v2/backend/helpers.py` → `vultron/adapters/driving/fastapi/helpers.py`

  No backward-compat shims. Updated cli.py, Dockerfile, and 9 test files.
  `vultron/api/` retains only `actor_io.py` (VCR-014), `trigger_services/` (VCR-D),
  and `datalayer/` package stub. 981 tests pass.

- [x] **VCR-016**: Evaluate `vultron/api/v2/data/utils.py` — determine whether
  utilities belong in `core/` (if core has duplicative needs) or in adapters
  (if adapter-only). Move to the correct location and update callers.
  All callers are adapter/demo layer (no core callers); moved to
  `vultron/adapters/utils.py`. Updated callers in `adapters/driven/datalayer_tinydb.py`,
  `api/v2/data/actor_io.py`, `demo/utils.py`, `demo/acknowledge_demo.py`,
  `demo/receive_report_demo.py`, and tests. Moved test to `test/adapters/test_utils.py`.
  981 tests pass.

#### Batch VCR-C — Core models and port cleanup

- [ ] **VCR-014**: Remove `vultron/api/v2/data/actor_io.py` after the role of
  in-memory inbox/outbox is resolved per ACT-1 ADR design decision. This file
  predates the DataLayer port abstraction and is not per-actor isolated.
  Resolution may be migration into DataLayer or formalization as a queue adapter.

- [x] **VCR-019c**: Study task — identify which enums across `case_states/` and
  `bt/**/states.py` can be consolidated. Be conservative: do NOT add or remove
  RM, EM, or CS model states. Document findings before implementing.
  **Done**: findings documented in `plan/IMPLEMENTATION_NOTES.md` (2026-03-18).
  Summary: no duplicates found; `RM`, `EM`, `CS`/sub-enums, `CVDRoles` are
  Group A (move to `vultron/core/states/`); `CvdStateModelError` hierarchy is
  Group B (merge into `vultron/errors.py`); scoring enums (`EmbargoViability`,
  SSVC, CVSS, etc.) are Group C (move with case_states/ but not to
  `core/states/`); `MessageTypes`, `CapabilityFlag`, `ActorState` are
  Group D (stay in bt/). See notes for full detail.

- [ ] **VCR-019a**: Move enums and state machine definitions from
  `vultron/case_states/` into `vultron/core/`. Integrate the error hierarchy
  from `case_states/` into the core error hierarchy. Do not leave compatibility
  shims behind. **Prerequisite: VCR-019c (done)** — see notes for
  implementation guidance and recommended target structure.

- [ ] **VCR-019b**: Move `states.py` enums from each `vultron/bt/**/` submodule
  (embargo management, report management, roles) into `vultron/core/states/`.
  Update all imports in `vultron/bt/`. Do not leave shims. `MessageTypes`,
  `CapabilityFlag`, and `ActorState` stay in bt/ (Group D per VCR-019c study).
  **Prerequisite: VCR-019c (done)** — see notes for implementation guidance.

- [ ] **VCR-019d** (future): Consider using the `transitions` module to model
  RM/EM/CS state machines once enum consolidation is complete. Defer until after
  VCR-019a/b/c are done.

- [ ] **VCR-019e**: Convert older non-StrEnum Enums to `StrEnum` where semantically
  appropriate (i.e., where string representation is the primary use). Apply
  selectively based on VCR-019c study results; do not blindly convert all enums.

- [ ] **VCR-020**: Ensure `VultronEvent.activity` is required (not `| None`) in
  the base class or narrow it to required in every concrete subclass that always
  carries an activity. Aligns with the fail-fast design constraint (ARCH-10-001).

- [ ] **VCR-021a**: Clarify whether `VultronActivity` (in
  `vultron/core/models/activity`) and `VultronEvent` (in
  `vultron/core/models/events/base.py`) are the same concept or distinct.
  If distinct, document the distinction clearly. If equivalent, consolidate.

- [ ] **VCR-021b**: Make core event model fields non-optional where the field is
  always present for that semantic type (e.g., `report` in
  `CreateReportReceivedEvent`, `case` in `CreateCaseReceivedEvent`).
  Fields typed as `X | None` that are never `None` in practice MUST be
  narrowed in the subclass. Batch with VCR-020.

- [ ] **VCR-022**: This is equivalent to **TECHDEBT-16** — add a `VultronObject`
  base class in `vultron/core/models/` so all domain model classes inherit from a
  single root rather than directly from `BaseModel`. The base class should capture
  common fields (`id`, `name`, `created_at`, `updated_at`, etc.) matching
  ActivityStreams object fields where appropriate. See TECHDEBT-16 entry above.

- [ ] **VCR-023**: Update `notes/architecture-ports-and-adapters.md` references
  to `delivery_queue.py` to reflect that the delivery-queue concept has been
  superseded by the emitter. Delete `vultron/core/ports/delivery_queue.py` after
  confirming no callers; `core/ports/emitter.py` (OX-1.0) is the correct
  replacement. Also update any code examples in the notes that reference
  `DeliveryQueue`.

- [ ] **VCR-025**: Evaluate whether `vultron/core/ports/dispatcher.py`
  (`ActivityDispatcher` Protocol) is still needed, or whether the `UseCase` port
  fully covers the dispatch contract. Do not remove without a validated migration
  plan and passing tests. Document the decision in AGENTS.md or an ADR.

- [ ] **VCR-026**: Ensure all port files in `core/ports/` are clearly labelled
  as inbound or outbound in their module docstrings. Remove ports that no longer
  correspond to active interfaces (see VCR-024, VCR-025).
  Cross-reference: `specs/architecture.md` ARCH-11-001.

- [ ] **VCR-027**: Evaluate `vultron/core/use_cases/_types.py` — determine
  whether the Protocol types defined there (`CaseModel`, `ParticipantModel`, etc.)
  belong in `vultron/core/models/` instead. If so, move them and update callers.
  This supports the goal of a clean domain model hierarchy (VCR-022/TECHDEBT-16).

- [x] **VCR-028**: Remove unnecessary `if _idempotent_create(...): return` guard
  patterns in use cases where the method return value already handles early exit.
  Changed `_idempotent_create` return type from `bool` to `None`; replaced
  all 10 `if _idempotent_create(...): return` guards in `actor.py` (4),
  `case_participant.py` (1), `embargo.py` (2), `note.py` (1), `status.py` (2)
  with direct calls. 981 tests pass.

- [ ] **VCR-029**: Equivalent to VCR-021b — make required fields on core event
  models non-optional. Captured in VCR-021b above.

#### Batch VCR-D — Trigger service cleanup

- [ ] **VCR-010**: Rename trigger service functions in
  `vultron/api/v2/backend/trigger_services/` from `svc_xxx` prefix to `xxx_trigger`
  suffix (e.g., `svc_engage_case` → `engage_case_trigger`). Update all callers.
  The `Svc` prefix is reserved for use-case class names only.

- [ ] **VCR-011**: Abstract the repeated `try: ... except VultronError: ...` pattern
  in `trigger_services/embargo.py`, `trigger_services/report.py`, and
  `trigger_services/case.py` into a shared decorator or context manager. Apply
  consistently across all trigger service functions.

- [ ] **VCR-012**: Review `vultron/api/v2/backend/trigger_services/_models.py` for
  models that duplicate or overlap with `vultron/core/models/` or
  `vultron/core/use_cases/_types.py`. Move duplicates to core and update callers.
  Most trigger request models should ultimately live in core.

#### Batch VCR-E — New feature: actor discovery endpoint

- [ ] **VCR-005**: Add `GET /actors/{actor_id}/profile` endpoint returning an
  ActivityStreams-style actor profile (inbox URL, outbox URL, profile fields) for
  actor discovery. This is required for multi-server discovery (PRIORITY-300).
  Add to the appropriate router in `adapters/driving/fastapi/` (or `api/v2/routers/`
  before the consolidation). Add tests. Document in `specs/agentic-readiness.md`
  or create a new spec if needed.

---

**Reference**: `specs/outbox.md` OX-03, OX-04

**Note**: Before OX-1.1, add `vultron/core/ports/emitter.py` — the
`ActivityEmitter` Protocol that driven delivery adapters implement.
Per `notes/architecture-ports-and-adapters.md` "Dispatch vs Emit Terminology",
this is the outbound counterpart to `core/ports/dispatcher.py`.

- [ ] **OX-1.0**: Add `vultron/core/ports/emitter.py` — `ActivityEmitter`
  Protocol stub (outbound counterpart to `core/ports/dispatcher.py`). Done when
  the Protocol is defined with at least an `emit(activity, recipients)` method
  and `adapters/driven/delivery_queue.py` references it as the port interface.
- [ ] **OX-1.1**: Implement local delivery: write activity from actor outbox to
  recipient actor's inbox in DataLayer (OX-04-001, OX-04-002). **Depends on OX-1.0.**
- [ ] **OX-1.2**: Integrate delivery as background task after handler completion
  (OX-03-002, OX-03-003); must not block HTTP response
- [ ] **OX-1.3**: Add idempotency check — delivering same activity twice MUST NOT
  create duplicate inbox entries (OX-06-001)
- [ ] **OX-1.4**: Add `test/api/v2/backend/test_outbox.py`

---

### PRIORITY-70 Complete ✅ — DataLayer in Ports and Adapters

P70-2 through P70-5 all complete. See `plan/IMPLEMENTATION_HISTORY.md`.

---

### PRIORITY-75 Complete ✅ — Business Logic in core/use_cases/

P75-1, P75-2, P75-2a, P75-2b, P75-2c, P75-3, P75-4-pre, P75-4 all complete.
See `plan/IMPLEMENTATION_HISTORY.md` for details. Remaining tasks:

- [x] **P75-4-pre**: Standardize use-case interface (**COMPLETE**)
- [x] **P75-4**: Convert all use cases to class interface; implement CLI/MCP adapters (**COMPLETE**)
- [x] **P75-5**: Removed `api/v1`; examples migrated to v2 (ADR-0011) (**COMPLETE**)

---

### Pre-P100 Prerequisite Tasks

These tasks MUST be completed before the first P100 (ACT-2) commit lands.
They are extracted from the 2026-03-17 Priority-100 readiness review.

**Source**: `plan/IDEAS.md` "Priority 100 pre-implementation Review" section.

#### PREPX-1 — Fix BT status string comparisons in `core/use_cases/case.py`

**Priority**: High (promoted from Deferred; brittle pattern in core P100 path)

- [x] **PREPX-1**: Replace `result.status.name != "SUCCESS"` string comparisons
  with `result.status != Status.SUCCESS` enum comparisons in
  `EngageCaseReceivedUseCase`, `DeferCaseReceivedUseCase`, and
  `CreateCaseReceivedUseCase` in `vultron/core/use_cases/case.py` (3 sites at
  approx. lines 84, 170, 206). Import `from py_trees.common import Status`.
  No logic change. Done when all three comparisons use the enum and tests pass.
  **COMPLETE.**

#### PREPX-2 — Remove `handlers/__init__.py` backward-compat shim layer

**Priority**: High (architectural layer that P100 handler changes must thread through)

- [x] **PREPX-2**: Delete `vultron/api/v2/backend/handlers/__init__.py` and
  `handlers/_shim.py` (the compatibility wrappers that re-export every use case
  as a thin wrapper around `XxxReceivedUseCase(dl).execute()`). Updated
  `test/api/v2/backend/test_handlers.py` and `test/api/test_reporting_workflow.py`
  to call use-case classes directly with `VultronEvent` objects. Done when the
  shim files are deleted, tests call use cases directly, and the test suite passes.
  **COMPLETE.**

#### PREPX-3 — Remove `DispatchEvent` and `InboundPayload` deprecated aliases

**Priority**: High (deprecated API in active test use — must follow PREPX-2)

- [x] **PREPX-3**: Remove the `DispatchEvent` deprecated wrapper from
  `vultron/types.py` (P75-2c) and the `InboundPayload` backward-compat alias
  from `vultron/core/models/events/__init__.py`. These are consumed only by the
  test files addressed in PREPX-2. Do after PREPX-2. Done when neither alias
  exists in the codebase, all tests pass, and no imports reference them.
  **Depends on PREPX-2.** **COMPLETE.**

---

### Phase PRIORITY-100 — Actor Independence (PRIORITY 100)

**Reference**: `plan/PRIORITIES.md` PRIORITY 100,
`specs/case-management.md` CM-01,
`notes/domain-model-separation.md` (Per-Actor DataLayer Isolation Options)

**Blocked by**: PRIORITY-70 (complete ✅), PREPX-1, PREPX-2, PREPX-3

- [ ] **ACT-1**: Draft ADR for per-actor DataLayer isolation — document options
  (Option B: TinyDB namespace prefix; MongoDB community for production),
  trade-offs, and migration path. The MongoDB approach is recommended for
  production-grade isolation; implement Option B first as an incremental step.

  **ACT-1 ADR MUST address the following design decisions** (added 2026-03-17):

  - **`get_datalayer` FastAPI DI strategy**: The current `get_datalayer()` is a
    zero-argument singleton factory injected via `Depends(get_datalayer)`. P100
    requires it to accept `actor_id`. Options: (1) closure lambda — preferred;
    (2) custom dependency class; (3) explicit parameter threading. Option 1 is
    simplest and supports future dynamic actor instantiation. The ADR must
    explicitly choose and document the pattern so ACT-2 applies it consistently
    across all route files and trigger endpoints.

  - **`actor_io.py` inbox/outbox ownership**: `vultron/api/v2/data/actor_io.py`
    is an in-memory inbox/outbox store predating the DataLayer port abstraction.
    P100 must resolve whether to migrate it into the per-actor DataLayer (actor
    inbox/outbox as first-class TinyDB collections) or formalize it as a separate
    in-process queue adapter wired to the `ActivityEmitter` port (OX-1.0/1.1).
    This decision directly affects ACT-2 scope.

  - **OUTBOX-1 scope boundary**: Determine whether OUTBOX-1 delivery is in-scope
    for P100 or deferred until per-actor DataLayer isolation is proved out.

- [ ] **ACT-2**: Implement per-actor DataLayer isolation per chosen design. Done
  when Actor A's DataLayer operations do not affect Actor B's state and tests
  confirm isolation. **Depends on ACT-1.**

- [ ] **ACT-3**: Update `get_datalayer` dependency and all handler tests to use
  per-actor DataLayer fixtures. **Depends on ACT-2.**

---

### Phase PRIORITY-200 — CaseActor Broadcast (PRIORITY 200)

**Blocked by**: OUTBOX-1

**Reference**: `specs/case-management.md` CM-06, `plan/PRIORITIES.md` PRIORITY 200

- [ ] **CA-1**: After OUTBOX-1, implement CaseActor broadcast in `update_case`
  handler — send ActivityStreams activity to each active `CaseParticipant`'s
  inbox (CM-06-001, CM-06-002).
- [ ] **CA-2**: Add `GET /actors/{case_actor_id}/action-rules` endpoint returning
  valid CVD actions for a named participant given current RM/EM/CS/VFD state
  (CM-07-001, AR-07-001, AR-07-002). Add tests.
- [ ] **CA-3**: Add tests verifying CaseActor notifies all participants on case
  state update.

---

### Phase PRIORITY-300 — Multi-Actor Demos (PRIORITY 300)

**Blocked by**: PRIORITY-100, PRIORITY-200

**Reference**: `plan/PRIORITIES.md` PRIORITY 300, `notes/demo-future-ideas.md`

- [ ] **D5-1**: Confirm PRIORITY-100 and PRIORITY-200 are complete; update design.
- [ ] **D5-2**: Demo Scenario 1 (finder + vendor): Dockerized with two actor
  containers + CaseActor container.
- [ ] **D5-3**: Demo Scenario 2 (finder + vendor + coordinator).
- [ ] **D5-4**: Demo Scenario 3 (ownership transfer + multi-vendor).
- [ ] **D5-5**: Integration tests and Docker Compose configs for each scenario.

---

## Deferred (Per PRIORITIES.md)

- **BT status comparison normalization** — ~~Deferred~~ **Promoted to
  PREPX-1** (see pre-P100 section below). Replace `result.status.name !=
  "SUCCESS"` string comparisons with `result.status == Status.SUCCESS` enum
  comparisons in `EngageCaseReceivedUseCase`, `DeferCaseReceivedUseCase`,
  `CreateCaseReceivedUseCase`. (Source: `plan/IMPLEMENTATION_NOTES.md` item 7)
- **`CloseCaseUseCase` wire-type construction** — Replace direct construction of
  `VultronActivity(as_type="Leave")` in `CloseCaseUseCase` with domain event emission
  through the `ActivityEmitter` port (OX-1.0). Defer until OX-1.0 is implemented.
  (Source: `plan/IMPLEMENTATION_NOTES.md` code-review item 8)
- **UseCase Protocol generic enforcement** — Decide on a consistent
  `UseCaseResult` Pydantic return envelope; enforce via mypy. Defer to after
  TECHDEBT-21/22. (Source: `plan/IMPLEMENTATION_NOTES.md` code-review item 9)
- **Production readiness** (request validation, health check readiness,
  idempotency, structured logging) — all `PROD_ONLY` or low-priority
- **Response generation** — See `specs/response-format.md` and history
- **EP-02/EP-03** — EmbargoPolicy API + compatibility evaluation (`PROD_ONLY`)
- **AR-01-003** — Unique `operation_id` on FastAPI routes (LOW)
- **AR-04/AR-05/AR-06** — Job tracking, pagination, bulk ops (`PROD_ONLY`)
- **Domain model separation** (CM-08) — needs ADR; see
  `notes/domain-model-separation.md`
- **Agentic AI integration** (Priority 1000) — out of scope until protocol
  foundation is stable
- **Fuzzer node re-implementation** (Priority 500) — see `notes/bt-fuzzer-nodes.md`
