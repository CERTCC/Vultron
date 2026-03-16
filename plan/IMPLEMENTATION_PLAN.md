# Vultron API v2 Implementation Plan

**Last Updated**: 2026-03-16 (refresh #39: Priority 80 phase identified; TECHDEBT-27/28 promoted
from deferred; execution groupings added)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Completed phase history is in `plan/IMPLEMENTATION_HISTORY.md`.

### Current Status Summary

**Test suite**: 893 passing, 5581 subtests, 5 warnings (2026-03-16, after P75-4)

**All 38 handlers implemented** (including `unknown`) — see `IMPLEMENTATION_HISTORY.md`.
**Trigger endpoints**: all 9 complete (P30-1–P30-6). **Demo scripts**: 12 scripts,
all dockerized in `docker-compose.yml`. **P75 phase**: ALL COMPLETE (P75-1 through
P75-4). All 38 handler use cases and 9 trigger use cases are class-based. CLI
(`vultron/adapters/driving/cli.py`) and MCP
(`vultron/adapters/driving/mcp_server.py`) driving adapters implemented.

**Active phase**: **PRIORITY-80** — technical debt cleanup and full hexagonal
architecture realization. TECHDEBT-17 through TECHDEBT-28 are the active tasks,
ordered by impact and dependency; see the Priority-80 section below.

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
TECHDEBT-15.

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
objects in `extractor.py` use the `Pattern` suffix. P75-4 and P75-5 remain.

### ✅ UseCase interface standardized (P75-4-pre — complete)

`UseCase[Req, Res]` Protocol defined in `vultron/core/ports/use_case.py`.
`UnknownUseCase` in `vultron/core/use_cases/unknown.py` is the reference
implementation; the old callable wrapper delegates to it for backward compat.
P75-4 MUST refactor every use case it touches to the class interface.

### ❌ api/v1 disposition not planned (P75-5)

`vultron/api/v1/` is a vocabulary-examples HTTP adapter (thin routers over
`wire/as2/vocab/examples/`; no business logic). Decision required: keep
as-is, formally deprecate, or remove. Captured as P75-5.

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

### ❌ DRY core domain models (TECHDEBT-16 — new gap)

`vultron/core/models/` domain classes independently repeat common fields
(`id`, `name`, timestamps). Per `notes/domain-model-separation.md` "DRY Core
Domain Models", a `VultronObject` base class should capture these fields;
`VultronEvent` and domain model classes should inherit from it.

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

- [ ] **P75-5**: Decide disposition of `vultron/api/v1/`. The v1 API is a
  vocabulary-examples HTTP adapter (thin routers over `wire/as2/vocab/examples/`;
  no business logic). Options: (a) keep as-is with a clear "vocabulary showcase"
  label, (b) merge into `api/v2` as a `/examples/` subrouter, or (c) deprecate
  and remove. Done when a decision is recorded in an ADR or issue and the code
  reflects the decision.

---

### Phase PRIORITY-80 — Technical Debt and Architecture Cleanup

**Reference**: `plan/PRIORITIES.md` PRIORITY 80

All P75 tasks are complete. This phase addresses accumulated technical debt and
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

- [ ] **TECHDEBT-16**: Add a `VultronObject` base class in `vultron/core/models/`
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

- [ ] **TECHDEBT-19**: Remove imports of `rehydrate` from
  `vultron.api.v2.data.rehydration` and `OfferStatus`, `ReportStatus`,
  `get_status_layer`, `set_status` from `vultron.api.v2.data.status` in
  `vultron/core/use_cases/triggers/report.py`. Core modules MUST NOT import from
  the application adapter layer. Move `rehydration.py` and/or `status.py` (or
  the relevant functions/types) to a neutral location in `vultron/core/` or
  promote them to the `DataLayer` port so core can use them without crossing
  the adapter boundary. Done when `triggers/report.py` has no imports from
  `vultron.api.v2.*`, the functionality is accessible from a core or shared
  location, and the test suite passes.

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

- [ ] **TECHDEBT-21**: Rename all handler use cases (those in `core/use_cases/`
  top-level modules: `actor.py`, `case.py`, `case_participant.py`, `embargo.py`,
  `note.py`, `report.py`, `status.py`) to append the `Received` suffix
  (e.g., `CreateReportUseCase` → `CreateReportReceivedUseCase`). Update
  `USE_CASE_MAP` in `core/use_cases/use_case_map.py` and all import sites and
  tests in the same commit. This is a mechanical rename with no behaviour change.
  Done when all ~32 handler use cases carry the `Received` suffix, the
  `USE_CASE_MAP` is updated, and the test suite passes.

---

### TECHDEBT-22 — Declare `UseCase[Req, Res]` Protocol base on every use case class

**Priority**: Medium (type safety, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 12

- [ ] **TECHDEBT-22**: Add `UseCase[RequestType, ResponseType]` as the explicit
  Protocol base for every use case class in `core/use_cases/`. Handler use cases
  return `None`; trigger use cases return `dict`. Example:

  ```python
  class CreateReportReceivedUseCase(UseCase["CreateReportReceivedEvent", None]):
      ...
  ```

  Done when every use case class explicitly inherits from the
  `UseCase` Protocol, mypy confirms structural conformance, and tests pass.
  **Depends on TECHDEBT-21** (rename must be done first for consistency).

---

### TECHDEBT-23 — Extract `TriggerRequest` base class in `triggers/requests.py`

**Priority**: Low (DRY, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 13

- [ ] **TECHDEBT-23**: Add a `TriggerRequest` base class in
  `vultron/core/use_cases/triggers/requests.py` with `model_config = ConfigDict(extra="ignore")`
  and `actor_id: NonEmptyString`. Have all 8 concrete trigger request models
  subclass `TriggerRequest` and remove the duplicated `model_config` and
  `actor_id` fields from each. Done when the base class is defined, all
  subclasses inherit it, the duplicate fields are removed, and tests pass.

---

### TECHDEBT-24 — Remove wire-layer imports from core use cases

**Files**: `core/use_cases/case.py` and `triggers/_helpers.py`

**Priority**: Medium (ARCH-06 violation, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 4

- [ ] **TECHDEBT-24**: Remove lazy import of `VulnerabilityCase` from
  `vultron.wire.as2.vocab.objects.vulnerability_case` in
  `core/use_cases/case.py`, and `VulnerabilityCase` / `ParticipantStatus`
  imports from the wire layer in `triggers/_helpers.py`. Replace with domain
  Protocol types from `core/use_cases/_types.py` or introduce a thin domain
  factory that core can call without importing wire types. Done when
  `core/use_cases/case.py` and `core/use_cases/triggers/_helpers.py` have no
  imports from `vultron.wire.*`, equivalent functionality is provided through
  domain interfaces, and tests pass.

---

### TECHDEBT-25 — Extract `_as_id()` helper to eliminate repeated pattern

**Priority**: Low (DRY, discovered in 2026-03-16 code review)

**Source**: `plan/IMPLEMENTATION_NOTES.md` "2026-03-16 code-review findings" item 5

- [ ] **TECHDEBT-25**: Extract a private helper function `_as_id(obj) -> str | None`
  (implementing `obj.as_id if hasattr(obj, "as_id") else str(obj) if obj is not None else None`)
  into `vultron/core/use_cases/_helpers.py` and replace all ~7 call sites in
  `case.py`, `actor.py`, `embargo.py`, and `case_participant.py`. Done when the
  helper exists, all repetitions are replaced, and tests pass.

---

### TECHDEBT-26 — Replace `OptionalNonEmptyString` alias with `NonEmptyString | None`

**Priority**: Low (cleanup, raised in `plan/IDEAS.md`)

**Source**: `plan/IDEAS.md` "Most strings in Pydantic objects should be NonEmptyStrings";
`specs/code-style.md` CS-08-002

- [ ] **TECHDEBT-26**: Remove the `OptionalNonEmptyString` type alias from
  `vultron/wire/as2/vocab/base/types.py` and `vultron/core/models/events/base.py`,
  replacing all usages with the equivalent inline form `NonEmptyString | None`.
  Update `specs/code-style.md` CS-08-002 accordingly once usages are removed.
  Done when `OptionalNonEmptyString` no longer appears anywhere in the codebase
  and tests pass.

---

### TECHDEBT-27 — Standardize error handling in use cases

**Priority**: Medium (un-deferred now that P75-4 is complete)

**Source**: `plan/IMPLEMENTATION_NOTES.md` code-review item 6 (deferred); promoted
from Deferred section after P75-4 completion.

- [ ] **TECHDEBT-27**: Remove silent `except Exception` swallowers from use cases;
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

- [ ] **TECHDEBT-28**: Extract a private helper `_idempotent_create(self, object_type,
  object_id, obj, label)` into a shared base class or module-level function in
  `vultron/core/use_cases/_helpers.py` (alongside the `_as_id()` helper from
  TECHDEBT-25). Replace the ~6 repetitions of the same idempotency guard pattern
  across `CreateEmbargoEventUseCase`, `CreateNoteUseCase`,
  `CreateCaseParticipantUseCase`, `CreateCaseStatusUseCase`,
  `CreateParticipantStatusUseCase`, and `SuggestActorToCaseUseCase`. Done when
  the helper exists, all repetitions are replaced, and tests pass.
  **Batch with TECHDEBT-25** (both add helpers to `_helpers.py`).

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

### Phase OUTBOX-1 — Outbox Local Delivery (lower priority)

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
- [ ] **P75-5**: Decide disposition of `vultron/api/v1/` (see above)

---

### Phase PRIORITY-100 — Actor Independence (PRIORITY 100)

**Reference**: `plan/PRIORITIES.md` PRIORITY 100,
`specs/case-management.md` CM-01,
`notes/domain-model-separation.md` (Per-Actor DataLayer Isolation Options)

**Blocked by**: PRIORITY-70 (complete ✅)

- [ ] **ACT-1**: Draft ADR for per-actor DataLayer isolation — document options
  (Option B: TinyDB namespace prefix; MongoDB community for production),
  trade-offs, and migration path. The MongoDB approach is recommended for
  production-grade isolation; implement Option B first as an incremental step.

- [ ] **ACT-2**: Implement per-actor DataLayer isolation per chosen design. Done
  when Actor A's DataLayer operations do not affect Actor B's state and tests
  confirm isolation.

- [ ] **ACT-3**: Update `get_datalayer` dependency and all handler tests to use
  per-actor DataLayer fixtures.

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

- **BT status comparison normalization** — Replace `result.status.name != "SUCCESS"`
  string comparisons with `result.status == Status.SUCCESS` enum comparisons in
  `EngageCaseUseCase`, `DeferCaseUseCase`, `CreateCaseUseCase`. (Source:
  `plan/IMPLEMENTATION_NOTES.md` code-review item 7)
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
