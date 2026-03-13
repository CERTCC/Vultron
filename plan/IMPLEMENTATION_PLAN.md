# Vultron API v2 Implementation Plan

**Last Updated**: 2026-03-13 (refresh #31: P75-2a/b/c tasks inserted before P75-3)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Completed phase history is in `plan/IMPLEMENTATION_HISTORY.md`.

### Current Status Summary

**Test suite**: 880 passing, 5581 subtests, 0 xfailed (2026-03-11, after P70-2)

**All 38 handlers implemented** (including `unknown`) — see `IMPLEMENTATION_HISTORY.md`.
**Trigger endpoints**: all 9 complete (P30-1–P30-6). **Demo scripts**: 12 scripts,
all dockerized in `docker-compose.yml`.

---

## Gap Analysis (2026-03-11, refresh #24)

### ✅ Previously completed (see `plan/IMPLEMENTATION_HISTORY.md`)

BUGFIX-1, REFACTOR-1, DEMO-3, DEMO-4, SPEC-COMPLIANCE-1, SPEC-COMPLIANCE-2,
SC-3.1, SC-PRE-1, TECHDEBT-1, TECHDEBT-5, TECHDEBT-6, TECHDEBT-10, TECHDEBT-11, P30-1,
P30-2, P30-3, P30-4, P30-5, P30-6, P50-0, ARCH-1.1, ARCH-1.2, ARCH-1.3,
ARCH-1.4, ARCH-CLEANUP-1, ARCH-CLEANUP-2, ARCH-CLEANUP-3, ARCH-ADR-9, P60-1,
P60-2, P60-3, TECHDEBT-3, TECHDEBT-7, TECHDEBT-8, TECHDEBT-9, TECHDEBT-10,
TECHDEBT-11, TECHDEBT-12, SC-PRE-2, SC-3.2, SC-3.3,
P65-1, P65-2, P65-3, P65-4, P65-5, P65-6a, P65-6b, P65-7.

### ❌ Outbox delivery not implemented (lower priority)

`actor_io.py` stub logs placeholder messages (OX-03-001, OX-04-001, OX-04-002).

### ✅ Triggerable behaviors fully implemented (PRIORITY 30 — COMPLETE)

All 9 trigger endpoints in split router files. P30-1 through P30-6 complete.

### ✅ Hexagonal architecture violations remediated (PRIORITY 65 — ALL COMPLETE)

All P65 tasks (P65-1 through P65-7) are complete. All violations V-01 through
V-23 are resolved:

- **V-03-R ✅ (P65-4)**: `behavior_dispatcher.py` has no runtime wire imports;
  `extract_intent()` moved to adapter layer in `inbox_handler.py`.
- **V-15/16/17/18/19 ✅ (P65-6b)**: Core BT nodes (`report/nodes.py`,
  `case/nodes.py`, `report/policy.py`, `case/create_tree.py`) use domain types
  from `vultron.core.models.vultron_types`; no wire-layer AS2 imports remain.
- **V-22/23 ✅ (P65-7)**: All core BT test files use domain type fixtures;
  `test_behavior_dispatcher.py` no longer imports wire types.

**⚠️ Stale docs**: `notes/architecture-review.md` still shows V-03-R, V-15–19,
V-22–23 as open/partial. ARCH-DOCS-1 task added to update these markers.

**Residual**: `test/core/behaviors/report/test_policy.py` still imports
`VulnerabilityReport` from `vultron.wire.as2.vocab.objects.vulnerability_report`
(policy tests pass via duck-typing). Captured in TECHDEBT-13.

### ✅ Package relocation Phase 1 complete (PRIORITY 60 — COMPLETE)

- `vultron/as_vocab/` → `vultron/wire/as2/vocab/` (P60-1 ✅)
- `vultron/behaviors/` → `vultron/core/behaviors/` (P60-2 ✅)
- `vultron/adapters/` package stub created (P60-3 ✅)

### ❌ DataLayer shims removed (PRIORITY 70 — Phase 1 COMPLETE ✅)

`vultron/api/v2/datalayer/abc.py`, `tinydb_backend.py`, and `db_record.py` have been
removed. All callers now import `DataLayer` from `vultron.core.ports.datalayer`,
`TinyDbDataLayer`/`get_datalayer`/`reset_datalayer` from
`vultron.adapters.driven.datalayer_tinydb`, and `Record`/`object_to_record` from
`vultron.adapters.driven.db_record`. P70-2 through P70-5 complete.

### ❌ Handlers and trigger services not yet extracted to core/use_cases/ (PRIORITY 75)

`vultron/api/v2/backend/handlers/` (2223 lines, 38 handlers) and
`vultron/api/v2/backend/trigger_services/` (1188 lines) contain domain
business logic that belongs in `vultron/core/use_cases/`. The
`vultron/core/use_cases/__init__.py` stub exists but is empty. Once extracted,
handlers and trigger-service functions become thin driving-adapter delegates
that call into core use cases. This also enables `adapters/driving/cli.py`
and `adapters/driving/mcp_server.py` to call the same use cases without going
through HTTP. See Phase PRIORITY-75.

### ❌ api/v1 disposition not planned

`vultron/api/v1/` is a vocabulary-examples HTTP adapter (returns `vocab_examples.*`
results; no real business logic). It is already architecturally compliant —
thin routers over `wire/as2/vocab/examples/`. No migration is needed.
Decision required: keep as-is, formally deprecate, or remove. Captured as P75-5.

### ❌ Actor independence not implemented (PRIORITY 100)

All actors share a singleton `TinyDbDataLayer` instance. PRIORITY 100 requires
per-actor isolated state. Options documented in `notes/domain-model-separation.md`
(Option B: TinyDB namespace prefix; MongoDB community edition for production).
Blocked by PRIORITY-70 (DataLayer relocation).

### ❌ CaseActor broadcast not implemented (PRIORITY 200)

CM-06-001 requires CaseActor to notify all case participants on case state update.
Blocked by OUTBOX-1.

### ✅ SPEC-COMPLIANCE-3 complete (SC-PRE-2, SC-3.2, SC-3.3 all done)

`SC-PRE-2`, `SC-3.2`, and `SC-3.3` are all complete. The `update_case` guard
checks participant embargo acceptance and logs a WARNING (CM-10-004); full
enforcement deferred to PRIORITY-200.

### ❌ `vultron/enums.py` backward-compat shim still present (TECHDEBT-4 / P70-2)

`vultron/enums.py` remains as a backward-compat re-export shim for `MessageSemantics`
plus defines `OfferStatusEnum` and `VultronObjectType`. These two domain-boundary
enums should eventually be relocated (`OfferStatusEnum` → `core/models/`,
`VultronObjectType` → `wire/as2/enums.py` or `core/models/`). `vultron/enums.py`
can then be deleted. Depends on completing PRIORITY-70. See P70-2.

### ❌ `vultron/core/ports/` missing delivery_queue and dns_resolver stubs (P70-3)

`vultron/adapters/driven/delivery_queue.py` and `dns_resolver.py` reference
`core/ports/delivery_queue.py` and `core/ports/dns_resolver.py` as their port
interfaces, but those Protocol stub files do not exist yet. P70-3 must add them.

### ❌ New violation V-24: `wire/as2/vocab/examples/_base.py` imports from adapter layer

`vultron/wire/as2/vocab/examples/_base.py` imports `DataLayer` from
`vultron.api.v2.datalayer.abc` at module level and `Record`, `get_datalayer` from
`api/v2/datalayer/` inside `initialize_examples()`. Wire layer must not import
from the adapter layer. Captured in TECHDEBT-13.

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
V-01 through V-23 resolved. See `plan/IMPLEMENTATION_HISTORY.md` for details.

---

### Phase SPEC-COMPLIANCE-3 — Embargo Acceptance Tracking (COMPLETE ✅)

SC-PRE-2, SC-3.2, SC-3.3 all complete. See `plan/IMPLEMENTATION_HISTORY.md`.

---

### Technical Debt (housekeeping) — all complete ✅

TECHDEBT-3, TECHDEBT-7, TECHDEBT-8, TECHDEBT-9, TECHDEBT-10, TECHDEBT-11,
TECHDEBT-12 all done. TECHDEBT-4 superseded by P70-2.
See `plan/IMPLEMENTATION_HISTORY.md`.

---

### ARCH-DOCS-1 — Update architecture-review.md violation status markers

**Priority**: High (docs correctness)

- [x] **ARCH-DOCS-1**: Update `notes/architecture-review.md` to mark V-03-R
  (P65-4), V-15/16/17/18/19 (P65-6b), and V-22/23 (P65-7) as fully resolved.
  Update the status header block at the top of the file to reflect the current
  state: all violations V-01 through V-23 resolved. Done when the file
  accurately reflects the post-P65-7 state and no violation is misrepresented
  as open or partial.

---

### TECHDEBT-13 — Minor wire-boundary cleanup items

**Priority**: Medium (architecture hygiene)

- [x] **TECHDEBT-13a**: Update `test/core/behaviors/report/test_policy.py` to
  replace the `VulnerabilityReport` import from `vultron.wire.as2.vocab.objects`
  with `VultronReport` from `vultron.core.models.vultron_types`. Done when no
  core test imports wire-layer AS2 vocabulary types and tests pass. (Residual
  V-23 cleanup.)
- [x] **TECHDEBT-13b**: Fix V-24 — update `vultron/wire/as2/vocab/examples/_base.py`
  to eliminate adapter-layer imports. The `DataLayer` annotation should use the
  core port (`vultron.core.ports.activity_store.DataLayer`); the `initialize_examples()`
  function should accept a `DataLayer` argument only (removing the `get_datalayer()`
  fallback and `Record` import). Done when `_base.py` has no imports from
  `vultron.api.v2.datalayer.*` and tests pass.
- [x] **TECHDEBT-13c**: Update `TYPE_CHECKING` imports in `vultron/types.py` and
  `vultron/behavior_dispatcher.py` to reference `vultron.core.ports.activity_store.DataLayer`
  directly instead of `vultron.api.v2.datalayer.abc.DataLayer` (the shim).
  Done when no `core/` or top-level module imports from `api/v2/datalayer/abc`
  at type-check time.

---

### TECHDEBT-14 — Split `vultron/core/models/vultron_types.py` into per-type modules

**Priority**: Low (organizational)

- [ ] **TECHDEBT-14**: Split `vultron/core/models/vultron_types.py` (273 lines,
  11 classes) into individual modules following the `wire/as2/vocab/objects/`
  pattern (e.g., `core/models/report.py`, `core/models/case.py`). Add a
  re-export shim at `vultron/core/models/vultron_types.py` for backward compat
  (similar to `api/v2/datalayer/abc.py`). Done when each type has its own
  module, re-exports work for existing callers, and tests pass.

---

### Phase PRIORITY-65 — Address Architecture Violations (ALL COMPLETE ✅)

All P65 tasks (P65-1 through P65-7) complete. All violations V-01 through V-23
resolved. See `plan/IMPLEMENTATION_HISTORY.md` for full task details.

---

### Phase BT-2.2/2.3 — Optional BT Refactors (low priority)

- [ ] **BT-2.2**: Refactor `close_report` handler to use BT tree
  (reference: `vultron/bt/report_management/_behaviors/close_report.py`)
- [ ] **BT-2.3**: Refactor `invalidate_report` handler to use BT tree
  (reference: `_InvalidateReport` subtree in `validate_report.py`)

---

### Phase OUTBOX-1 — Outbox Local Delivery (lower priority)

**Reference**: `specs/outbox.md` OX-03, OX-04

- [ ] **OX-1.1**: Implement local delivery: write activity from actor outbox to
  recipient actor's inbox in DataLayer (OX-04-001, OX-04-002)
- [ ] **OX-1.2**: Integrate delivery as background task after handler completion
  (OX-03-002, OX-03-003); must not block HTTP response
- [ ] **OX-1.3**: Add idempotency check — delivering same activity twice MUST NOT
  create duplicate inbox entries (OX-06-001)
- [ ] **OX-1.4**: Add `test/api/v2/backend/test_outbox.py`

---

### Phase PRIORITY-70 — DataLayer Refactor into Ports and Adapters

**Reference**: `plan/PRIORITIES.md` PRIORITY 70,
`notes/domain-model-separation.md` (Per-Actor DataLayer Isolation Options),
`notes/architecture-ports-and-adapters.md`

**P70-1 SUPERSEDED by P65-1** — DataLayer Protocol move to `core/ports/` done.
**Must precede**: PRIORITY-100 (actor independence uses the new layer structure).

- [x] **P70-2**: Move `OfferStatusEnum` and `VultronObjectType` from
  `vultron/enums.py` to their correct architectural homes (`core/models/` and
  `wire/as2/enums.py` respectively). Delete `vultron/enums.py`. Update all
  callers (about 13 files import from `vultron.enums`). Done when no
  `vultron.enums` imports remain and tests pass.

- [x] **P70-3**: Add `vultron/core/ports/delivery_queue.py` and
  `vultron/core/ports/dns_resolver.py` Protocol stub files. The stubs in
  `vultron/adapters/driven/delivery_queue.py` and `dns_resolver.py` already
  reference these as their port interfaces but the files do not yet exist.
  No implementation logic required — Protocol class definitions only. Done when
  both files exist in `core/ports/` and the driven adapter stubs can import from
  them without errors.

- [x] **P70-4**: Move `vultron/api/v2/datalayer/tinydb_backend.py` (the TinyDB
  implementation) to `vultron/adapters/driven/activity_store.py`. Leave a
  backward-compat re-export shim at the old path. Update `api/v2/datalayer/abc.py`
  shim to re-export from the new location. Done when `TinyDbDataLayer` lives in
  `adapters/driven/`, all imports resolve, and tests pass.

- [x] **P70-5**: Remove shims and update all remaining callers to import
  `TinyDbDataLayer` from `adapters/driven/` and `DataLayer` from
  `core/ports/activity_store`. Delete `api/v2/datalayer/abc.py` and the
  `api/v2/datalayer/tinydb.py` re-export shim. Done when no module imports from
  `vultron.api.v2.datalayer.*` and tests pass. **Depends on P70-4.**

---

### Phase PRIORITY-75 — api/v2 Business Logic → core/use_cases/

**Reference**: `plan/PRIORITIES.md` PRIORITY 60/65 ("continue hex arch refactor"),
`notes/architecture-ports-and-adapters.md`,
`vultron/core/use_cases/__init__.py` (stub docstring)

**Must precede**: PRIORITY-100 (driving adapters need clean use-case interface).
**Blocked by**: PRIORITY-70 (use cases call core ports; DataLayer must be
fully relocated first).

- [x] **P75-1**: Define the `VultronEvent` domain event base type and initial
  subclasses (e.g., `ReportCreatedEvent`, `CaseEngagedEvent`, `EmbargoInvitedEvent`)
  in `vultron/core/models/events.py`. These replace `DispatchActivity` as the
  input type for use-case callables. Done when domain event types cover the
  38 handler semantics, have no wire or adapter imports, and pass type checks.

- [x] **P75-2**: Extract handler business logic from
  `vultron/api/v2/backend/handlers/*.py` into `vultron/core/use_cases/`. Each
  handler file (`report.py`, `case.py`, `embargo.py`, `participant.py`, etc.)
  gets a matching module in `core/use_cases/` containing plain callables that
  accept a `VultronEvent` and a `DataLayer` port. The adapter-layer handler
  becomes a thin delegate: verifies semantics, builds the domain event, calls
  the use case. Done when `core/use_cases/` covers all 38 use cases, handlers
  import from `core/use_cases/`, and tests pass. **Depends on P75-1.**

  > ⚠️ **Post-P75-2 architecture tangles** (resolve before P75-3):
  > The dispatch pipeline has residual wire coupling, vestigial handler delegates,
  > naming inconsistency (Activity vs Event), and the dispatcher has not yet been
  > modelled as a formal driving port. P75-2a–2c resolve these before
  > trigger-service extraction adds more code on top.

- [ ] **P75-2a** — Core domain model audit and enrichment: Audit every `Vultron*`
  domain type in `vultron/core/models/vultron_types.py` against its wire
  counterpart — `VultronReport` vs `VulnerabilityReport`, `VultronCase` vs
  `VulnerabilityCase`, `VultronEmbargoEvent` vs `EmbargoEvent`,
  `VultronParticipant` vs `CaseParticipant`, `VultronNote` vs `as_Note`,
  `VultronCaseStatus` vs `CaseStatus`, `VultronParticipantStatus` vs
  `ParticipantStatus`, `VultronActivity` vs `as_Activity`. For each pair,
  identify every field present in the wire model but absent from the domain
  model — especially pass-through fields (`content`, `summary`, `url`, `tag`,
  `media_type`, `context`, etc.) that may appear in real activities but are not
  yet represented. Add the missing fields to the domain models. Update
  `extract_intent()` in `vultron/wire/as2/extractor.py` to populate all new
  fields during wire-to-domain translation. Add or update tests that verify the
  new fields survive the wire-to-domain round-trip. Done when every semantically
  relevant wire-model field is captured in the corresponding domain model or
  documented as intentionally excluded, and tests pass.
  **Must precede P75-2b** — removing `wire_object` pass-through (P75-2b) only
  makes sense once domain models contain all the data use cases need.
  **Depends on P75-1, P75-2.**

- [ ] **P75-2b** — Remove wire coupling from the dispatch envelope and rename
  `DispatchActivity` → `DispatchEvent`:
  - Rename `DispatchActivity` to `DispatchEvent` in `vultron/types.py`. "Activity"
    is a wire-layer concept; "Event" is a domain-layer concept. Update all
    references (dispatcher, inbox handler, handler files, tests, specs, AGENTS.md).
    Note: `EmbargoEvent` is an AS2 object type, not a `VultronEvent` subclass —
    take care with naming in that vicinity.
  - Remove `wire_activity: Any` and `wire_object: Any` from `DispatchEvent`.
    These opaque wire fields leak the wire layer into the dispatch envelope.
    Once domain models are enriched (P75-2a), the `VultronEvent` payload carries
    all data use cases need.
  - Remove `wire_object` and `wire_activity` keyword parameters from every use
    case function in `vultron/core/use_cases/`. Use cases must operate on
    `VultronEvent` + `DataLayer` only.
  - Update `prepare_for_dispatch()` in `inbox_handler.py` to not carry wire
    objects into the envelope.
  - Update the `BehaviorHandler` Protocol in `vultron/types.py` (or wherever it
    lands after P75-2c) to use `DispatchEvent`.
  - Update `specs/dispatch-routing.md` and `specs/handler-protocol.md` to reflect
    the rename and the removal of wire fields.
  - Done when `DispatchActivity` is fully renamed to `DispatchEvent`, it has no
    wire-layer fields, and no use case function accepts wire objects. Tests pass.
  **Depends on P75-2a.**

- [ ] **P75-2c** — Model dispatcher as formal driving port, flatten the handler
  adapter layer, and rename pattern objects:
  - **Driving port**: Move the `ActivityDispatcher` Protocol from `vultron/types.py`
    to `vultron/core/ports/dispatcher.py`. A driving port is an interface the core
    *exposes* for adapters to call into it; defining it in `core/ports/` alongside
    `DataLayer` makes this role explicit and makes the concrete dispatcher
    injectable (e.g., in tests). Signature: `dispatch(event: VultronEvent, dl:
    DataLayer) -> None` (after P75-2b removes wire fields from `DispatchEvent`).
  - **Routing table to core**: Move `SEMANTICS_HANDLERS` from
    `vultron/api/v2/backend/handler_map.py` to `vultron/core/use_cases/use_case_map.py`.
    This mapping from `MessageSemantics` (domain) to use case callables (domain)
    is domain knowledge, not adapter configuration. The driving-adapter inbox
    handler just calls the port; it need not know which use case handles which
    semantic.
  - **Dispatcher implementation**: Move `DispatcherBase` / `DirectActivityDispatcher`
    from `vultron/behavior_dispatcher.py` to `vultron/core/` (e.g.,
    `vultron/core/dispatcher.py`) or to `vultron/adapters/driving/dispatcher.py`.
    Document the choice. The inbox adapter instantiates the concrete dispatcher
    and injects it (removing the module-level singleton pattern).
  - **Flatten handler layer**: Update `SEMANTICS_HANDLERS` (now in
    `core/use_cases/use_case_map.py`) to map `MessageSemantics` directly to use
    case callables. The `vultron/api/v2/backend/handlers/` shim modules become
    dead code; delete them. Confirm the `@verify_semantics` guard is either
    absorbed into the dispatcher (type assertion before invoking use case) or
    replaced by static type checking (mypy/pyright).
  - **Pattern naming**: Rename every `ActivityPattern` instance in
    `SEMANTICS_ACTIVITY_PATTERNS` in `vultron/wire/as2/extractor.py` to use a
    `Pattern` suffix (e.g., `CreateReport` → `CreateReportPattern`,
    `EngageCase` → `EngageCasePattern`). This distinguishes pattern-matching
    objects from similarly-named `Activity` and `Event` types.
  - Update AGENTS.md, specs, and inline documentation to reflect the new
    driving-port model and the absence of the handler shim layer.
  - Done when `ActivityDispatcher` is defined in `core/ports/`, routing table is
    in `core/use_cases/use_case_map.py`, handler shim modules are deleted, all
    pattern objects use `Pattern` suffix, and tests pass.
  **Depends on P75-2b.**

- [ ] **P75-3**: Migrate trigger-service logic from
  `vultron/api/v2/backend/trigger_services/` to `vultron/core/use_cases/`.
  The trigger router stays in `api/v2/routers/trigger_*.py`; the service layer
  moves to `core/use_cases/` as callable functions accepting domain types + a
  `DataLayer` port. Done when trigger services in `api/v2/backend/trigger_services/`
  are either deleted or reduced to thin delegates, and tests pass.
  **Depends on P75-1, P75-2.**

- [ ] **P75-4**: Update driving adapter stubs (`vultron/adapters/driving/cli.py`,
  `vultron/adapters/driving/mcp_server.py`) to call `core/use_cases/` callables
  directly with an injected `DataLayer`, without going through HTTP. Done when
  the CLI and MCP adapters exercise the same code paths as the HTTP inbox adapter.
  **Depends on P75-2, P75-3.**

- [ ] **P75-5**: Decide disposition of `vultron/api/v1/`. The v1 API is a
  vocabulary-examples HTTP adapter (thin routers over `wire/as2/vocab/examples/`;
  no business logic). Options: (a) keep as-is with a clear "vocabulary showcase"
  label, (b) merge into `api/v2` as a `/examples/` subrouter, or (c) deprecate
  and remove. Done when a decision is recorded in an ADR or issue and the code
  reflects the decision.

---

### Phase PRIORITY-100 — Actor Independence (PRIORITY 100)

**Reference**: `plan/PRIORITIES.md` PRIORITY 100,
`specs/case-management.md` CM-01,
`notes/domain-model-separation.md` (Per-Actor DataLayer Isolation Options)

**Blocked by**: PRIORITY-70

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
