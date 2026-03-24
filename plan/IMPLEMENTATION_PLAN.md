# Vultron API v2 Implementation Plan

**Last Updated**: 2026-03-24 (refresh #50: TECHDEBT-39 complete)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Completed phase history is in `plan/IMPLEMENTATION_HISTORY.md`.

**Priority ordering note:** `plan/PRIORITIES.md` is authoritative for project
priority. Section order in this file groups related work and execution context;
it does not override `plan/PRIORITIES.md` when the two differ.

### Current Status Summary

**Test suite**: 988 passed, 5581 subtests (2026-03-24).

**All 38 handlers implemented** (including `unknown`) — see `IMPLEMENTATION_HISTORY.md`.
**Trigger endpoints**: all 9 complete (P30-1–P30-6). **Demo scripts**: 12 scripts,
all dockerized in `docker-compose.yml`. **P75 phase**: ALL COMPLETE (P75-1
through P75-5). `api/v1` removed; vocabulary examples consolidated into
`vultron/adapters/driving/fastapi/routers/examples.py` (ADR-0011). All 38
handler use cases and 9 trigger use cases are class-based. CLI
(`vultron/adapters/driving/cli.py`) and MCP
(`vultron/adapters/driving/mcp_server.py`) driving adapters implemented.
**TECHDEBT-16 complete**: `VultronObject` base class defined in
`vultron/core/models/base.py`; all 12 domain object models inherit from it.
**P85 complete**: all IDEAS.md items captured in specs, notes, and plan.
**P90 COMPLETE**: All P90 tasks (P90-1 through P90-5) done. RM state
now fully persisted via DataLayer; global STATUS dict removed; transition
validity guards applied; OPP-06 spec captured in `specs/`.
**TECHDEBT-31 complete**: `trigger_services/` relocated into
`vultron/adapters/driving/fastapi/`; `vultron/api/v2/` now contains only
`data/actor_io.py` (pending VCR-014) and two `__init__.py` stubs.

**Active phases**: **PRIORITY-80** (technical debt cleanup) and
**PRIORITY-100** (actor independence — pre-requisites PREPX-1/2/3 and P90
all complete). TECHDEBT-16 through TECHDEBT-33 complete; TECHDEBT-32b complete
(34–37 still open); VCR-A batch (8/8 tasks) complete. VCR-B batch complete.
VCR-019a/b/c/e complete — state enums in `vultron/core/states/`;
`vultron/case_states/` removed; errors merged into `vultron/errors.py`.
OX-1.4 complete. BUG-001 (outbox_handler missing return) documented in
`plan/BUGS.md`; TECHDEBT-38 added to fix it. TECHDEBT-39 added for OPP-05
participant RM helper consolidation. TECHDEBT-32/32b complete: all
`object_to_record` / `save_to_datalayer` usages in core removed; `dl.save()`
is now the sole save pattern in core. TECHDEBT-32c complete: `get_datalayer`
fallback removed from `wire/as2/rehydration.py`; `dl` is now required.

---

## Gap Analysis (2026-03-23, refresh #45)

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
TECHDEBT-15, TECHDEBT-21, TECHDEBT-22, TECHDEBT-24, TECHDEBT-27, P75-5,
TECHDEBT-16, TECHDEBT-17, TECHDEBT-18, TECHDEBT-19, TECHDEBT-20, TECHDEBT-23,
TECHDEBT-25, TECHDEBT-26, TECHDEBT-28,
VCR-001, VCR-003, VCR-004, VCR-005, VCR-006, VCR-007, VCR-008, VCR-009,
VCR-010, VCR-011, VCR-012, VCR-015a, VCR-015b, VCR-016, VCR-017, VCR-018,
VCR-019a, VCR-019b, VCR-019c, VCR-019e, VCR-020, VCR-021a, VCR-021b,
VCR-022, VCR-023, VCR-024, VCR-025, VCR-026, VCR-027, VCR-028, VCR-029,
VCR-030, VCR-031, VCR-032,
PREPX-1, PREPX-2, PREPX-3, ACT-1, OX-1.0,
DOCS-1, DOCS-2, P90-2, P90-3.

### ❌ Outbox delivery not implemented (lower priority)

The outbound `ActivityEmitter` port is in place, but delivery work beyond
OX-1.0 is still pending. Local inbox/outbox delivery, background delivery
execution, idempotent delivery, and remote delivery remain open (OX-1.1+).

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

### ✅ Core use-case migration complete (PRIORITY 75)

All 38 handler use cases and 9 trigger-service use cases now live in
`vultron/core/use_cases/`. The old handler shim layer has been removed. The
dispatcher is modelled as a formal driving port (`core/ports/dispatcher.py`)
backed by `core/dispatcher.py`, and the routing table (`USE_CASE_MAP`) lives
in `core/use_cases/use_case_map.py`. Pattern objects in `extractor.py` use the
`Pattern` suffix. P75-4 and P75-5 complete.

### ✅ UseCase interface standardized (P75-4-pre — complete)

`UseCase[Req, Res]` Protocol defined in `vultron/core/ports/use_case.py`.
`UnknownUseCase` in `vultron/core/use_cases/unknown.py` is the reference
implementation; the old callable wrapper delegates to it for backward compat.
P75-4 MUST refactor every use case it touches to the class interface.

### ✅ api/v1 removed (P75-5 — COMPLETE)

`vultron/api/v1/` removed. Vocabulary-example endpoints migrated to
`vultron/adapters/driving/fastapi/routers/examples.py`. Decision recorded in
ADR-0011.

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

### ✅ ADR-0013 / PRIORITY-90 complete (P90-1 through P90-5)

All five P90 tasks are done. `START → RECEIVED` RM transition is now persisted
on report receipt; `RM.VALID` is seeded at case creation; transition-validity
guards (`is_valid_rm_transition()`, `is_valid_em_transition()`, etc.) are in
place in `core/states/` and enforced in use cases, trigger helpers, and the
wire-layer `append_rm_state()`; the global `STATUS` dict has been removed; and
OPP-06 spec requirements captured in `specs/behavior-tree-integration.md`
(BT-12-001). OPP-01, OPP-02, OPP-03 EM machine uses are also complete (see
TECHDEBT-34 updated notes). Remaining state-machine opportunities — OPP-05
(duplicate RM helpers) and OPP-06 (VFD/PXA callers, future) — are captured
as TECHDEBT-39 and noted as deferred respectively.

### ❌ BUG-001 — `outbox_handler` crashes on missing actor (TECHDEBT-38)

`vultron/adapters/driving/fastapi/outbox_handler.py` logs a warning when
`dl.read(actor_id)` returns `None` but does not `return` early; the next line
would raise `AttributeError`. See `plan/BUGS.md`. Fix captured as TECHDEBT-38.

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

### ✅ Broken inline code examples in `docs/` (DOCS-2 — resolved)

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

**Priority**: 95 (docs correctness, `notes/codebase-structure.md`)

- [x] **DOCS-1**: Update `docker/README.md` to accurately describe the current
  `docker-compose.yml` services: `api-dev` (API server), `demo` (unified demo
  runner for all demo scripts), `test` (pytest), `docs` (MkDocs), and
  `vultrabot-demo`. Remove references to individual per-demo service containers
  (e.g., `receive-report-demo`, `initialize-case-demo`, etc.) that have been
  consolidated into the `demo` service. Done when the README accurately reflects
  the current services and how to run them.

---

### DOCS-2 — Fix broken inline code examples in `docs/`

**Priority**: 85 (docs correctness, `notes/codebase-structure.md`)

- [x] **DOCS-2**: Update `docs/reference/code/as_vocab/*.md` files that reference
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

### New Technical Debt — 2026-03-20 Review

These tasks were identified during the 2026-03-20 planning session. All are
part of PRIORITY-80 cleanup unless otherwise noted.

#### TECHDEBT-29 — VCR-005 follow-up: profile endpoint returns only links

**Priority**: Medium (spec correctness, discovered in code review 2026-03-20)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "VCR-005 Follow-up" (2026-03-20)

- [x] **TECHDEBT-29**: Clarify and enforce that `GET /actors/{actor_id}/profile`
  returns an actor profile whose `inbox` and `outbox` fields are **URL links
  only** (not the collection contents). Ensure this is unambiguous in
  `specs/agentic-readiness.md` (AR-10-001–003) and add a test asserting that
  the response contains string URLs for `inbox` and `outbox`, not embedded
  collection objects. Done when the spec is updated, a test validates the
  constraint, and the test passes.

---

#### TECHDEBT-30 — Replace AS2-generic field names in core event interfaces

**Priority**: Medium (domain clarity, CS-12-001)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "wire-layer terminology leaking into
core" (2026-03-20); `notes/domain-model-separation.md`

- [x] **TECHDEBT-30**: Added domain-specific `@property` getters to all 22
  per-semantic event subclasses via reusable mixins in
  `vultron/core/models/events/_mixins.py`. Each mixin exposes one
  domain-specific property (e.g., `report_id`, `case_id`, `embargo_id`,
  `offer_id`, `invite_id`, `participant_id`, `note_id`, `status_id`,
  `invitee_id`) that aliases the appropriate generic base-class field. Updated
  all 7 use-case modules (`report.py`, `actor.py`, `embargo.py`,
  `case_participant.py`, `note.py`, `status.py`, `case.py`) to access the
  domain properties instead of the generic `object_id` / `target_id` /
  `context_id` / `inner_*` names. 984 tests pass.

---

#### TECHDEBT-31 — Relocate `trigger_services/` into FastAPI adapter

**Priority**: High (architectural cleanup, must complete before ACT-2)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "vultron.api.v2.backend.trigger_services
should go away" (2026-03-20); `notes/codebase-structure.md`

- [x] **TECHDEBT-31**: Move the contents of
  `vultron/api/v2/backend/trigger_services/` into `vultron/adapters/driving/fastapi/`:

  1. Move `domain_error_translation()` and `translate_domain_errors()` from
     `_helpers.py` into `vultron/adapters/driving/fastapi/errors.py`.
     Remove the re-export shim block from `_helpers.py`.
  2. Move HTTP request body models from `_models.py` to
     `vultron/adapters/driving/fastapi/trigger_models.py`.
  3. Inline the thin adapter delegates from `case.py`, `embargo.py`, and
     `report.py` directly into the corresponding router files
     (`routers/trigger_case.py`, `routers/trigger_embargo.py`,
     `routers/trigger_report.py`) or into a new sibling `_trigger_adapter.py`.
  4. Delete `vultron/api/v2/backend/trigger_services/` entirely.
  5. Update all imports and tests. No shims.

  After this task, `vultron/api/v2/` should contain only `data/actor_io.py`
  (pending VCR-014) and two `__init__.py` stubs. Done when
  `trigger_services/` is gone, all routers work, and tests pass.

---

#### TECHDEBT-32 — Research and plan core/DataLayer boundary refactor

**Priority**: Medium (architectural health, prerequisite to ACT-2)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "lack of clean separation at the
core to datalayer port and adapter boundaries" (2026-03-20);
`notes/domain-model-separation.md`

- [x] **TECHDEBT-32**: Audit the core/DataLayer boundary to understand the
  current coupling. Produce a written analysis (add to
  `notes/domain-model-separation.md` or a new `notes/datalayer-refactor.md`)
  that:
  1. Lists all places where `object_to_record()`, `record_to_object()`, or
     `find_in_vocabulary()` are called from core or wire (not adapter) code.
  2. Lists all places where core branches on DataLayer return types.
  3. Proposes the minimal refactoring needed so that the DataLayer port
     contract is typed in terms of core domain objects.
  4. Identifies whether `Record`/`StorableRecord` in `db_record.py` should be
     revised, promoted, or replaced.
  5. Identifies the vocabulary registry entanglement in `db_record.py` and
     `rehydration.py` and proposes decoupling.

  Done when the analysis document is committed and a follow-up implementation
  task (TECHDEBT-32b) is added to this plan based on the findings.
  **No code changes in this task — research and planning only.**

  **COMPLETE**: Analysis written to `notes/datalayer-refactor.md`. Found 2
  core-imports-adapter violations (`triggers/embargo.py`,
  `triggers/_helpers.py` importing `object_to_record` from adapter) and 1
  wire-imports-adapter violation (`rehydration.py` importing `get_datalayer`
  from TinyDB adapter). `Record`/`StorableRecord` hierarchy is sound.
  TECHDEBT-32b (code fix) implemented in same commit; TECHDEBT-32c (wire fix)
  added as follow-up. 985 tests pass.

- [x] **TECHDEBT-32b**: Remove `object_to_record` adapter imports from core
  trigger modules and replace all three save patterns with `dl.save(obj)`:
  1. Remove `from vultron.adapters.driven.db_record import object_to_record`
     from `triggers/embargo.py` and `triggers/_helpers.py`. Replace 5
     `dl.update(obj.as_id, object_to_record(obj))` calls with `dl.save(obj)`.
  2. Replace 4 `save_to_datalayer(self.datalayer, obj)` calls in BT nodes
     (`case/nodes.py`, `report/nodes.py`) with `self.datalayer.save(obj)`.
  3. Delete `save_to_datalayer()` helper from
     `vultron/core/behaviors/helpers.py` (no callers remain).

  Done when no core module imports from `vultron.adapters.driven.db_record`,
  all `object_to_record` and `save_to_datalayer` usages in core are gone,
  and 985 tests pass.

  **COMPLETE**: All 5 `object_to_record` sites and 4 `save_to_datalayer`
  sites replaced with `dl.save()`. `save_to_datalayer` function deleted.
  985 tests pass.

- [x] **TECHDEBT-32c**: Remove `from vultron.adapters.driven.datalayer_tinydb
  import get_datalayer` from `vultron/wire/as2/rehydration.py`. The wire
  layer must not import directly from the TinyDB adapter. Make `dl` a
  required parameter in `rehydrate()`, or inject a core-level factory port.
  All production callers already pass `dl` explicitly; the fallback exists
  only for legacy test paths. Done when no wire module imports from
  `vultron.adapters.driven.*` and 985 tests pass.

  **COMPLETE**: Removed `get_datalayer` import; made `dl: DataLayer` a
  required positional parameter. Updated three callers (`cli.py`,
  `fastapi/routers/datalayer.py`, `fastapi/inbox_handler.py`) to pass `dl`
  explicitly. Removed 25 legacy `monkeypatch.setattr(rehydration.get_datalayer)`
  stubs from 6 test files. 985 tests pass.

---

#### TECHDEBT-33 — Refactor `test/api/v2/backend/test_handlers.py`

**Priority**: Medium (test maintainability)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "Refactor large tests" (2026-03-20)

- [x] **TECHDEBT-33**: Split `test/api/v2/backend/test_handlers.py` into
  per-module test files mirroring the source layout under
  `test/core/use_cases/` (which is where the tested code now lives). The
  current file tests all 38 handler use cases in one place; it no longer maps
  to `api/v2/backend/handlers/` (which was deleted in PREPX-2). New layout:
  `test/core/use_cases/test_report.py`, `test_case.py`, `test_embargo.py`,
  `test_actor.py`, `test_case_participant.py`, `test_note.py`, `test_status.py`.
  Move tests without changing test logic. Done when the monolithic file is
  deleted and equivalent coverage is provided by the new per-module files.

---

#### TECHDEBT-34 — Sweep for remaining procedural EM/RM state logic to migrate to `transitions` machines

**Priority**: Medium (part of VCR-019d; architectural consistency)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "VCR-019d is largely addressed…"
(2026-03-20); `notes/state-machine-findings.md`

**2026-03-23 update**: OPP-01 (`SvcProposeEmbargoUseCase`), OPP-02
(`SvcTerminateEmbargoUseCase`), and OPP-03 (move `PROPOSED → ACTIVE`
transition out of wire layer) are all **complete** — the EM machine is
used in both trigger use cases and `set_embargo()` no longer mutates
`em_state`. EM transitions in `embargo.py` (use cases) that assign
`em_state = EM.ACTIVE` directly do so in core use-case code (not wire
layer), which is correct architecture.

Remaining work is RM-specific (OPP-04 context: STATUS layer removed by P90-4,
so RM guards now apply only to the DataLayer path) and any other hand-rolled
direct enum assignments in `vultron/core/` that bypass machine validation.

- [x] **TECHDEBT-34**: Verify and document any remaining hand-rolled RM or
  EM direct enum assignments in `vultron/core/use_cases/` and
  `vultron/core/behaviors/` (excluding those already guarded via
  `is_valid_rm_transition()` / `is_valid_em_transition()` in the call chain).
  For each unguarded site, either add a transition-validity guard or replace
  with machine-driven logic using the adapter pattern from
  `notes/state-machine-findings.md`. Done when all unguarded direct
  `em_state =` / `rm_state =` assignments in `vultron/core/` either have
  an explicit machine guard or a documented justification for bypassing it,
  and the test suite passes.
  **COMPLETE** (2026-03-24): Three unguarded `em_state = EM.ACTIVE` sites
  found and addressed:
  1. `SvcEvaluateEmbargoUseCase` (trigger-side) now uses `EMAdapter`+machine
     with `MachineError` → `VultronConflictError` (consistent with
     `SvcProposeEmbargoUseCase` and `SvcTerminateEmbargoUseCase`).
  2. `AddEmbargoEventToCaseReceivedUseCase` (receive-side) now checks
     `is_valid_em_transition()` and logs a WARNING if the transition is
     non-standard; proceeds regardless (state-sync override — documented
     justification for bypassing the hard guard).
  3. `AcceptInviteToEmbargoOnCaseReceivedUseCase` (receive-side) — same
     pattern as #2.
  All `rm_state=RM.XXX` assignments in `vultron/core/` are constructor
  arguments for new `VultronParticipantStatus` objects (initial-state
  constructions, not transitions); the `append_rm_state()` guard
  (`is_valid_rm_transition()`) already enforces RM transition validity for
  all mutation paths. 4 new tests added. 988 tests pass.

---

#### TECHDEBT-35 — Expand `_mixins.py` with richer domain properties

**Priority**: Low (cleanup, raised in `plan/IDEAS.md`)

**Source**: `plan/IDEAS.md` "Expand use of `vultron.core.models.events._mixins`"

- [x] **TECHDEBT-35**: Extend `vultron/core/models/events/_mixins.py` in two
  ways:

  1. **Add rich-object property to each `ObjectIsFoo` mixin**: Each existing
     mixin exposes `foo_id` (e.g., `report_id`) based on `object_id`. Add a
     `foo` property that returns the richer domain object (not just the ID).
     Use cases that need both the ID and the full object should find both
     available via the mixin rather than implementing the lookup ad hoc.

  2. **Add `HasActivityMixin`**: Many event classes carry an
     `activity: VultronActivity` field. Extract this into a reusable mixin
     that adds the `activity` field and any related helper methods, so event
     classes can compose it rather than repeating the field declaration.

  Done when: all `ObjectIsFoo` mixins expose a `foo` property alongside
  `foo_id`, a `HasActivityMixin` exists, all event classes that carry an
  `activity` field use it, and the test suite passes.

---

#### TECHDEBT-36 — Centralize `_make_payload()` test helper

**Priority**: Low (test DRY, raised in `plan/IMPLEMENTATION_NOTES.md`)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "`_make_payload()` duplicated across tests"

- [x] **TECHDEBT-36**: Multiple test files under `test/` contain a local
  `_make_payload(activity, **extra_fields)` helper function that was duplicated
  during a large test-file split. Identify all copies, extract the shared
  implementation into a centralized test fixture (e.g., a helper in
  `test/conftest.py` or a `test/helpers.py` utility module), and replace all
  local copies with imports of the shared version. Done when no duplicate
  `_make_payload` definitions remain and all affected tests pass.
  **COMPLETE**: Removed local `_make_payload` from 5 test files
  (`test_status_use_cases.py`, `test_actor_use_cases.py`, `test_note_use_cases.py`,
  `test_case_use_cases.py`, `test_embargo_use_cases.py`). All 37 affected test
  methods now use the `make_payload` fixture from `test/core/use_cases/conftest.py`.
  985 tests pass.

---

#### TECHDEBT-37 — Migrate `test/api/` tests to new layout

**Priority**: Low (structural cleanup; `vultron/api/v2/` is deprecated)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "`vultron/api/v2` is deprecated"

- [ ] **TECHDEBT-37**: `test/api/` contains tests that mirror the now-deprecated
  `vultron/api/v2/` layout. Migrate all tests in `test/api/` to the canonical
  layout that mirrors `vultron/adapters/driving/fastapi/` and
  `vultron/core/use_cases/` (e.g., move to `test/adapters/driving/fastapi/`
  or `test/core/use_cases/`). Remove `test/api/` once all tests are relocated.
  **Depends on VCR-014** (which removes the last live code under
  `vultron/api/v2/`). Done when `test/api/` is empty/removed, all tests are
  in the correct location, and the full test suite passes.

---

#### TECHDEBT-38 — Fix `outbox_handler` crash on missing actor (BUG-001)

**Priority**: Low (defensive correctness; see `plan/BUGS.md` BUG-001)

**Source**: `plan/BUGS.md` BUG-001 (discovered during OX-1.4 test writing,
2026-03-23)

- [x] **TECHDEBT-38**: In
  `vultron/adapters/driving/fastapi/outbox_handler.py`, add a `return` (or
  `return None`) immediately after the `logger.warning(...)` line that fires
  when `actor is None`. Without this early return, the next line
  (`while actor.outbox.items:`) raises `AttributeError: 'NoneType' object has
  no attribute 'outbox'` for any unknown `actor_id`. Done when the early return
  is present, the existing `test_outbox.py` test that covers the missing-actor
  path passes, and the full test suite passes.
  **COMPLETE**: The early return was already present in the code (applied as
  part of OX-1.4 work); plan entry was not yet checked off. Verified 985 tests pass.

---

#### TECHDEBT-39 — Consolidate duplicate participant RM state helper functions (OPP-05)

**Priority**: Low-Medium (reduces duplication; see
`notes/state-machine-findings.md` OPP-05)

**Source**: `notes/state-machine-findings.md` OPP-05 (duplicate RM helpers)

- [x] **TECHDEBT-39**: Two near-duplicate functions implement the "append a
  new `VultronParticipantStatus` with a given RM state" operation:

  1. `_find_and_update_participant_rm()` in
     `vultron/core/behaviors/report/nodes.py` (lines ~715+) — used by BT nodes
     `TransitionParticipantRMtoAccepted` and `TransitionParticipantRMtoDeferred`
  2. `update_participant_rm_state()` in
     `vultron/core/use_cases/triggers/_helpers.py` (lines ~57+) — used by
     `SvcEngageCaseUseCase` and `SvcDeferCaseUseCase`

  Consolidate into a single shared helper in
  `vultron/core/use_cases/triggers/_helpers.py` (or a new
  `vultron/core/use_cases/_participant_helpers.py`). Update BT node imports
  accordingly. Done when only one implementation exists, both BT nodes and
  trigger use cases use it, and the test suite passes.
  **COMPLETE**: Removed `_find_and_update_participant_rm()` wrapper from
  `nodes.py`. Both BT node `update()` methods now call `update_participant_rm_state()`
  directly (imported from `vultron.core.use_cases.triggers._helpers`), inlining
  the bool→Status conversion and exception handling. Removed redundant local
  `from vultron.core.states.rm import RM` imports inside the methods (RM is
  already imported at module level). 988 tests pass.

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
- [x] **VCR-030**: Delete `vultron/sim/` module — moved `Message` class to
  `vultron/bt/messaging/message.py`; updated all 4 callers in `vultron/bt/` to
  import from the new location; deleted `vultron/sim/`. 982 tests pass.
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

- [x] **VCR-019a**: Move enums and state machine definitions from
  `vultron/case_states/` into `vultron/core/`. Integrate the error hierarchy
  from `case_states/` into the core error hierarchy. Do not leave compatibility
  shims behind. **Prerequisite: VCR-019c (done)** — see notes for
  implementation guidance and recommended target structure.

- [x] **VCR-019b**: Move `states.py` enums from each `vultron/bt/**/` submodule
  (embargo management, report management, roles) into `vultron/core/states/`.
  Created `rm.py` (RM, RM_CLOSABLE, RM_UNCLOSED, RM_ACTIVE), `em.py` (EM),
  `roles.py` (CVDRoles, add_role). Updated `__init__.py` and all 59 callers.
  Deleted original `states.py` files. No shims. 982 tests pass.

- [x] **VCR-019d**: Consider using the `transitions` module to model
  RM/EM/CS state machines once enum consolidation is complete.

- [x] **VCR-019e**: Convert older non-StrEnum Enums to `StrEnum` where semantically
  appropriate (i.e., where string representation is the primary use). Apply
  selectively based on VCR-019c study results; do not blindly convert all enums.
  **Done**: Converted 6 `IntEnum` components in `vultron/core/states/cs.py`
  (`VendorAwareness`, `FixReadiness`, `FixDeployment`, `PublicAwareness`,
  `ExploitPublication`, `AttackObservation`) from `IntEnum` to `StrEnum`
  using single-letter values (v/V, f/F, d/D, p/P, x/X, a/A). Converted
  `MessageTypes` in `vultron/bt/messaging/states.py` from `Enum` to `StrEnum`
  and removed redundant `VULTRON_MESSAGE_EMBARGO_REVISION_*` entries (EV, EJ,
  EC are now explicit aliases for EP, ER, EA). Updated `EM_MESSAGE_TYPES` to
  remove duplicate entries. Updated tests accordingly. 982 tests pass.

- [x] **VCR-020**: Added `activity: VultronActivity | None = None` to
  `VultronEvent` base class. Subclasses that always carry an activity already
  narrowed it to required (no default). This satisfies ARCH-10-001 (fail-fast):
  the base permits `None` for semantics that don't use the field; subclasses
  that always populate `activity` make it required. 982 tests pass.

- [x] **VCR-021a**: `VultronActivity` and `VultronEvent` are distinct concepts.
  Updated docstrings in `vultron/core/models/activity.py` and
  `vultron/core/models/events/base.py` to document the distinction clearly:
  `VultronActivity` is the domain model for DataLayer storage of AS2 activity
  objects; `VultronEvent` is the semantic dispatch event carrying decomposed
  ID/type fields used for handler routing. 982 tests pass.

- [x] **VCR-021b**: Verified all concrete domain object fields in event
  subclasses are already non-optional where always present (`report`,
  `case`, `embargo`, `participant`, `note`, `status`, `activity`). No
  `X | None` fields exist in subclasses where the value is always set.
  982 tests pass.

- [x] **VCR-022**: Equivalent to **TECHDEBT-16** — already complete.
  `VultronObject` base class is defined in `vultron/core/models/base.py`
  and all 10 domain model classes inherit from it
  (`VultronActivity`, `VultronCase`, `VultronCaseActor`, `VultronCaseStatus`,
  `VultronEmbargoEvent`, `VultronNote`, `VultronParticipant`,
  `VultronParticipantStatus`, `VultronReport`, `VultronActivity` subtypes).
  Verified 2026-03-19; no code changes needed.

- [x] **VCR-023**: Deleted `vultron/core/ports/delivery_queue.py` and
  `vultron/adapters/driven/delivery_queue.py` (no callers). Updated
  `notes/architecture-ports-and-adapters.md`: removed both files from tree
  listings, replaced `DeliveryQueue` code example with `DataLayer`-based
  example, moved removed ports to a 'removed' section. 982 tests pass.

- [x] **VCR-025**: Evaluated `ActivityDispatcher` Protocol in
  `vultron/core/ports/dispatcher.py`. **Decision: keep it.** It is actively
  used in `vultron/core/dispatcher.py` (return type of `get_dispatcher()`) and
  `vultron/adapters/driving/fastapi/inbox_handler.py` (module-level type
  annotation). `ActivityDispatcher.dispatch(event, dl)` and `UseCase[Req, Res]`
  serve distinct roles: the dispatcher routes an event to a use case; the use
  case executes a single operation. They cannot be collapsed into one. Decision
  documented in `plan/IMPLEMENTATION_NOTES.md`.

- [x] **VCR-026**: Updated module docstrings in all four `core/ports/` files to
  explicitly label each port as inbound (driving) or outbound (driven) per
  `specs/architecture.md` ARCH-11-001. `dispatcher.py` and `use_case.py` are
  **inbound (driving)**; `datalayer.py` is **outbound (driven)**. `__init__.py`
  now lists the full port taxonomy with descriptions. No ports removed (VCR-024
  and VCR-023 already handled removals; VCR-025 confirmed `ActivityDispatcher`
  is retained). 982 tests pass.

- [x] **VCR-027**: Moved `CaseModel` and `ParticipantModel` Protocol types from
  `vultron/core/use_cases/_types.py` to `vultron/core/models/protocols.py`.
  Updated all 7 callers (`triggers/_helpers.py`, `case_participant.py`,
  `embargo.py`, `case.py`, `actor.py`, `note.py`, `status.py`) to import from
  `vultron.core.models.protocols`. Deleted `_types.py`. 982 tests pass.

- [x] **VCR-028**: Remove unnecessary `if _idempotent_create(...): return` guard
  patterns in use cases where the method return value already handles early exit.
  Changed `_idempotent_create` return type from `bool` to `None`; replaced
  all 10 `if _idempotent_create(...): return` guards in `actor.py` (4),
  `case_participant.py` (1), `embargo.py` (2), `note.py` (1), `status.py` (2)
  with direct calls. 981 tests pass.

- [x] **VCR-029**: Equivalent to VCR-021b — verified complete. All required
  fields on core event models are non-optional. Captured in VCR-021b above.

#### Batch VCR-D — Trigger service cleanup

- [x] **VCR-010**: Renamed all 9 trigger service functions in
  `vultron/api/v2/backend/trigger_services/` from `svc_xxx` prefix to `xxx_trigger`
  suffix (e.g., `svc_engage_case` → `engage_case_trigger`). Updated all callers in
  `adapters/driving/fastapi/routers/` and `test/api/v2/backend/test_trigger_services.py`.
  982 tests pass.

- [x] **VCR-011**: Abstract the repeated `try: ... except VultronError: ...` pattern
  in `trigger_services/embargo.py`, `trigger_services/report.py`, and
  `trigger_services/case.py` into a shared decorator or context manager. Apply
  consistently across all trigger service functions.

- [x] **VCR-012**: Reviewed `vultron/api/v2/backend/trigger_services/_models.py`.
  Core domain trigger request models already live in `vultron/core/use_cases/triggers/requests.py`
  (completed as TECHDEBT-23); `_models.py` is correctly the HTTP adapter layer.
  Eliminated duplicated URI validation: extracted `UriString = Annotated[NonEmptyString,
  AfterValidator(_valid_uri)]` into `vultron/core/models/base.py` alongside `NonEmptyString`.
  Updated `requests.py` to import `UriString` from `base.py` (removing its own
  `_URI_SCHEME_RE`, `_valid_uri`, `CaseIdString`). Updated `_models.py` to use
  `UriString` and `NonEmptyString` from core (removing 4 duplicated `case_id_must_be_uri`
  validators and the `_URI_SCHEME_RE` pattern). Also tightened `offer_id` and `note`
  fields to `NonEmptyString` in `_models.py`. 982 tests pass.

#### Batch VCR-E — New feature: actor discovery endpoint

- [x] **VCR-005**: Add `GET /actors/{actor_id}/profile` endpoint returning an
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

- [x] **OX-1.0**: Add `vultron/core/ports/emitter.py` — `ActivityEmitter`
  Protocol stub (outbound counterpart to `core/ports/dispatcher.py`). Done when
  the Protocol is defined with at least an `emit(activity, recipients)` method
  and `adapters/driven/delivery_queue.py` references it as the port interface.
  **COMPLETE**: `ActivityEmitter` Protocol defined in `core/ports/emitter.py`;
  stub `DeliveryQueueAdapter` in `adapters/driven/delivery_queue.py` imports
  and implements the Protocol. 984 tests pass.
- [ ] **OX-1.1**: Implement local delivery: write activity from actor outbox to
  recipient actor's inbox in DataLayer (OX-04-001, OX-04-002). **Depends on OX-1.0.**
- [ ] **OX-1.2**: Integrate delivery as background task after handler completion
  (OX-03-002, OX-03-003); must not block HTTP response
- [ ] **OX-1.3**: Add idempotency check — delivering same activity twice MUST NOT
  create duplicate inbox entries (OX-06-001)
- [x] **OX-1.4**: Add `test/api/v2/backend/test_outbox.py`

---

### PRIORITY-70 Complete ✅ — DataLayer in Ports and Adapters

P70-2 through P70-5 all complete. See `plan/IMPLEMENTATION_HISTORY.md`.

---

### PRIORITY-75 Complete ✅ — Business Logic in core/use_cases/

P75-1, P75-2, P75-2a, P75-2b, P75-2c, P75-3, P75-4-pre, P75-4 all complete.
See `plan/IMPLEMENTATION_HISTORY.md` for details. Remaining tasks:

- [x] **P75-4-pre**: Standardize use-case interface (**COMPLETE**)
- [x] **P75-4**: Convert all use cases to class interface; implement CLI/MCP
  adapters (**COMPLETE**)
- [x] **P75-5**: Removed `api/v1`; examples migrated to v2 (ADR-0011) (**COMPLETE**)

---

### Phase PRIORITY-85 — snapshot of previous IDEAS.md (COMPLETE ✅)

**Reference**: `plan/PRIORITIES.md` Priority 85

All items from `plan/IDEAS.md` have been extracted and captured:

- Action items → `plan/IMPLEMENTATION_PLAN.md` tasks (VCR-0317 batch, PREPX-*,
  P90-*, TECHDEBT-*)
- Requirements → `specs/` (ARCH-09, ARCH-10, ARCH-11, CS-08-002, CS-12-001/2,
  TB-05-*, AR-10-*, etc.)
- Design insights → `notes/` (`architecture-ports-and-adapters.md`,
  `domain-model-separation.md`, `state-machine-findings.md`, etc.)
- Resolved entries struck through in `ideas/IDEAS.md`; file now reset to 2
  lines (header only).
- DOCS-2 complete (required for CI to pass before merging).

---

### Phase PRIORITY-90 — ADR-0013 and State-Machine Follow-up (ALL COMPLETE ✅)

**Reference**: `plan/PRIORITIES.md` Priority 90,
`docs/adr/0013-unify-rm-state-tracking.md`,
`notes/state-machine-findings.md` (OPP-06, OPP-07, OPP-09)

This phase captures the RM-state unification and state-machine follow-up work.

**2026-03-23 status**: ALL COMPLETE — P90-1, P90-2, P90-3, P90-4, P90-5 done.
OPP-01, OPP-02, OPP-03 EM machine integrations also complete. Remaining
state-machine opportunities deferred or captured: OPP-05 → TECHDEBT-39,
OPP-06 → BT-12-001 spec requirement (deferred until VFD/PXA callers needed).

- [x] **P90-1**: Persist initial RM report-phase state in
  `VultronParticipantStatus` (persisted) rather than the transient in-memory
  STATUS dict. In `CreateReportReceivedUseCase` and `SubmitReportReceivedUseCase`,
  after persisting the report, create and persist a `VultronParticipantStatus`
  record with `rm_state=RM.RECEIVED` for the receiving actor in addition to
  (or instead of) calling `set_status()`. This is the explicit
  `START → RECEIVED` (RECEIVE trigger) transition required by ADR-0013 step 1.
  Done when report-receipt creates a persisted participant status entry and
  the full RM history is queryable from the DataLayer.
  **Depends on: nothing (can start immediately).**
  **COMPLETE** — `_report_phase_status_id()` helper added; both use cases
  persist a `VultronParticipantStatus` with `rm_state=RM.RECEIVED`,
  `context=report_id`, `attributed_to=actor_id`. Idempotent via UUID v5
  deterministic ID. 3 new tests added; 987 tests pass.

- [x] **P90-2**: Carry validated RM state into case creation. When a case is
  created from a valid report, seed the actor's case-phase participant history
  with `RM.VALID` rather than `RM.START`. **COMPLETE** —
  `vultron/core/behaviors/case/nodes.py` `CreateInitialVendorParticipantNode`
  now seeds `rm_state=RM.VALID` (commit `8921b41`). 996 tests pass.

- [x] **P90-3**: Use shared transition validation for persisted RM, EM, VFD,
  and PXA updates. `is_valid_rm_transition()`, `is_valid_em_transition()`, and
  `is_valid_pxa_transition()` added to `vultron/core/states/`. Guards added in
  `AddCaseStatusToCaseReceivedUseCase`, `AddParticipantStatusToParticipantReceivedUseCase`
  (`core/use_cases/status.py`), `update_participant_rm_state()` (triggers),
  and `_find_and_update_participant_rm()` (behaviors). **COMPLETE** — 996 tests
  pass.

- [x] **P90-4**: Remove transient STATUS-layer dependencies once P90-1 persisted
  RM history is authoritative. After P90-1 is complete and covered by tests,
  delete STATUS dict reads/writes in `core/use_cases/report.py` and
  `core/use_cases/triggers/report.py`. Remove the `STATUS` global dict from
  `core/models/status.py` and the `ReportStatus`, `set_status()`,
  `get_status_layer()` helpers once no callers remain. Done when
  `core/models/status.py` no longer contains a global mutable dict and
  all RM state is read from the DataLayer. **Depends on: P90-1.**
  **COMPLETE** — `STATUS` dict, `ReportStatus`, `set_status()`,
  `get_status_layer()` removed from `status.py`. BT nodes (`CheckRMStateValid`,
  `CheckRMStateReceivedOrInvalid`, `TransitionRMtoValid`, `TransitionRMtoInvalid`)
  updated to use DataLayer. Trigger use cases updated. All 5 affected test files
  updated to use DataLayer assertions. 984 tests pass.

- [x] **P90-5**: Capture OPP-06 requirements in `specs/behavior-tree-integration.md`.
  Added section `BT-12 VFD/PXA State Machine Usage` with requirement `BT-12-001`
  and verification criteria. Markdownlint passes. **COMPLETE** (commit `2d4308e`).

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

- [x] **ACT-1**: Draft ADR for per-actor DataLayer isolation — document options
  (Option B: TinyDB namespace prefix; MongoDB community for production),
  trade-offs, and migration path. **COMPLETE**: `docs/adr/0012-per-actor-datalayer-isolation.md`
  documents all four design decisions: isolation strategy (Option B — TinyDB
  namespace prefix, with concurrent MongoDB), DI pattern (closure lambda),
  `actor_io.py` ownership (migrate into DataLayer as inbox/outbox collections;
  remove `actor_io.py` after ACT-2), and OUTBOX-1 scope (defer until ACT-3
  complete). ADR-0012 status: accepted.

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
  through the `ActivityEmitter` port. Defer until outbound delivery integration
  beyond OX-1.0 is implemented. (Source: `plan/IMPLEMENTATION_NOTES.md`
  code-review item 8)
- **UseCase Protocol generic enforcement** — Decide on a consistent
  `UseCaseResult` Pydantic return envelope; enforce via mypy. Defer to after
  TECHDEBT-21/22. (Source: `plan/IMPLEMENTATION_NOTES.md` code-review item 9)
- **Production readiness** (request validation, idempotency, structured logging) — all `PROD_ONLY` or low-priority
- ~~**OB-05-002 readiness probe**~~ — **COMPLETE** (commit `2d4308e`)
- **Response generation** — See `specs/response-format.md` and history
- **EP-02/EP-03** — EmbargoPolicy API + compatibility evaluation (`PROD_ONLY`)
- ~~**AR-01-003**~~ — **COMPLETE**: unique `operation_id` on all FastAPI routes (commit `2d4308e`)
- **AR-04/AR-05/AR-06** — Job tracking, pagination, bulk ops (`PROD_ONLY`)
- **Domain model separation** (CM-08) — needs ADR; see
  `notes/domain-model-separation.md`
- **Agentic AI integration** (Priority 1000) — out of scope until protocol
  foundation is stable
- **Fuzzer node re-implementation** (Priority 500) — see `notes/bt-fuzzer-nodes.md`
