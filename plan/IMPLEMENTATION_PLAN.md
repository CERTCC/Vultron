# Vultron API v2 Implementation Plan

**Last Updated**: 2026-03-11 (P65-6a complete: VultronEvent hierarchy; extract_intent() returns typed subclasses)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Completed phase history is in `plan/IMPLEMENTATION_HISTORY.md`.

### Current Status Summary

**Test suite**: 880 passing, 5581 subtests, 0 xfailed (2026-03-11, after P65-6a)

**All 38 handlers implemented** (including `unknown`):
create_report, submit_report, validate_report (BT), invalidate_report, ack_report,
close_report, engage_case (BT), defer_case (BT), create_case (BT),
add_report_to_case, close_case, create_case_participant,
add_case_participant_to_case, invite_actor_to_case,
accept_invite_actor_to_case, reject_invite_actor_to_case,
remove_case_participant_from_case, create_embargo_event,
add_embargo_event_to_case, remove_embargo_event_from_case,
announce_embargo_event_to_case, invite_to_embargo_on_case,
accept_invite_to_embargo_on_case, reject_invite_to_embargo_on_case,
create_note, add_note_to_case, remove_note_from_case, create_case_status,
add_case_status_to_case, create_participant_status,
add_participant_status_to_participant, suggest_actor_to_case,
accept_suggest_actor_to_case, reject_suggest_actor_to_case,
offer_case_ownership_transfer, accept_case_ownership_transfer,
reject_case_ownership_transfer, update_case

**Trigger endpoints** (P30-1 through P30-6 complete — all 9 endpoints):
`validate-report`, `invalidate-report`, `reject-report`, `engage-case`, `defer-case`,
`close-report`, `propose-embargo`, `evaluate-embargo`, `terminate-embargo`

**Demo scripts** (all dockerized in `docker-compose.yml`):
`receive_report_demo.py`, `initialize_case_demo.py`, `invite_actor_demo.py`,
`establish_embargo_demo.py`, `status_updates_demo.py`, `suggest_actor_demo.py`,
`transfer_ownership_demo.py`, `acknowledge_demo.py`, `manage_case_demo.py`,
`initialize_participant_demo.py`, `manage_embargo_demo.py`,
`manage_participants_demo.py`

---

## Gap Analysis (2026-03-11, refresh #23)

### ✅ Previously completed (see `plan/IMPLEMENTATION_HISTORY.md`)

BUGFIX-1, REFACTOR-1, DEMO-3, DEMO-4, SPEC-COMPLIANCE-1, SPEC-COMPLIANCE-2,
SC-3.1, SC-PRE-1, TECHDEBT-1, TECHDEBT-5, TECHDEBT-6, TECHDEBT-10, TECHDEBT-11, P30-1,
P30-2, P30-3, P30-4, P30-5, P30-6, P50-0, ARCH-1.1, ARCH-1.2, ARCH-1.3,
ARCH-1.4, ARCH-CLEANUP-1, ARCH-CLEANUP-2, ARCH-CLEANUP-3, ARCH-ADR-9, P60-1,
P60-2, P60-3.

### ❌ Outbox delivery not implemented (lower priority)

`actor_io.py` stub logs placeholder messages (OX-03-001, OX-04-001, OX-04-002).

### ✅ Triggerable behaviors fully implemented (PRIORITY 30 — COMPLETE)

All 9 trigger endpoints in split router files. P30-1 through P30-6 complete.

### ⚠️ Hexagonal architecture has active regressions (PRIORITY 50 / PRIORITY 65)

A review of the codebase (2026-03-10) revealed that ARCH-1.x remediations
were **incomplete or regressed**. The following violations have since been
addressed through P65-1 through P65-3 and P65-5:

- **V-02-R / V-11-R** ✅ **(P65-3)**: `InboundPayload.raw_activity: Any` removed.
  `InboundPayload` now carries 13 typed domain fields. Handlers read exclusively
  from `dispatchable.payload` and `dispatchable.wire_activity` / `wire_object`
  (opaque adapter-layer fields). `extract_intent()` in `wire/as2/extractor.py`
  is the sole AS2→domain mapping point.
- **V-03-R**: `behavior_dispatcher.py` still imports
  `from vultron.wire.as2.extractor import find_matching_semantics, extract_intent`
  (line 10) — the `extract_intent` call must move to the adapter layer (P65-4).
- **V-10-R** ✅ **(P65-2)**: `inbox_handler.py` lifespan-managed DataLayer injection
  implemented; module-level instantiation and per-call mutation removed.
- **V-20 / V-21** ✅ **(P65-2 / P65-3)**: Lazy `SEMANTICS_HANDLERS` import in
  `DispatcherBase.__init__()` removed; `handler_map` is now required at
  construction. `.model_dump_json()` on `raw_activity` removed from `dispatch()`.

Remaining new violations introduced in `vultron/core/behaviors/` by P60-2:

- V-13/14 ✅ **(P65-1)**: Resolved — `DataLayer` moved to `core/ports/`.
- V-15/16/17/18/19: Core BT nodes still import AS2 wire types (`VulnerabilityCase`,
  `CreateCase`, etc.) and `ParticipantStatus`; V-16/V-18 partial resolved (P65-5).
  Full resolution deferred to P65-6.

V-22 partially resolved (test no longer uses `raw_activity`; `as_Create` import
remains for `prepare_for_dispatch` test — will be moved with P65-4).
V-23 resolved by P65-7 ✅ (core BT test files now use domain type fixtures).

**All P65 tasks complete. ✅**

### ✅ Package relocation Phase 1 complete (PRIORITY 60 — P60-1, P60-2, and P60-3 DONE)

- `vultron/as_vocab/` → `vultron/wire/as2/vocab/` (P60-1 ✅)
- `vultron/behaviors/` → `vultron/core/behaviors/` (P60-2 ✅)
- `vultron/adapters/` package stub created (P60-3 ✅)

### ✅ Test directory layout updated after package relocation (TECHDEBT-11 DONE)

`test/as_vocab/` → `test/wire/as2/vocab/` and `test/behaviors/` →
`test/core/behaviors/` relocated to mirror the new source layout. Old directories
removed. 841 tests pass. ✅ 2026-03-10

### ✅ Deprecated FastAPI status constant in trigger services (TECHDEBT-12 DONE)

All `HTTP_422_UNPROCESSABLE_ENTITY` usages replaced with
`HTTP_422_UNPROCESSABLE_CONTENT` across `trigger_services/`. ✅ 2026-03-10

### ⚠️ Architecture violations partially remediated (PRIORITY 65)

P65-1, P65-2, P65-3, P65-5 complete. V-02-R and V-11-R resolved (P65-3);
V-03-R remains (P65-4). V-13/V-14 resolved (P65-1); V-15/V-16/V-18 partially
resolved (P65-5); V-17/V-19 and full V-15/V-18 deferred to P65-6b.
V-20/V-21 resolved as side effects of P65-2/P65-3.
Phase PRIORITY-65 remaining tasks: P65-6b (core BT node AS2 removal), P65-7 (test regressions).
**P65-1 replaces P70-1.**

### ❌ DataLayer not yet relocated to adapters layer (PRIORITY 70)

`vultron/api/v2/datalayer/` should be moved to reflect the hexagonal architecture:
the `DataLayer` Protocol belongs in `vultron/core/ports/` and the TinyDB
implementation in `vultron/adapters/driven/`. Currently still under `api/v2/`.
Per `notes/domain-model-separation.md`, this relocation SHOULD be planned
together with PRIORITY 100 (actor independence). Blocked by P60-3 (adapters
package must be stubbed first). See Phase PRIORITY-70.

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

### ✅ CS-08-001 — Optional string fields reject empty strings (TECHDEBT-7/9 DONE)

`NonEmptyString` and `OptionalNonEmptyString` type aliases applied across
all `Optional[str]` fields in `vultron/wire/as2/vocab/objects/`. Per-field
empty-string validators replaced with shared types. ✅ 2026-03-10

### ✅ Pyright static type checking configured (TECHDEBT-8 DONE)

No `pyrightconfig.json` exists. `specs/tech-stack.md` IMPL-TS-07-002 requires
pyright adoption with a gradual approach.

### ✅ Object IDs standardized to URI form (TECHDEBT-3 DONE)

`generate_new_id()` now returns `urn:uuid:{uuid}` by default. `BASE_URL` in
`vultron/api/v2/data/utils.py` is configurable via `VULTRON_BASE_URL` env var.
DataLayer compatibility shim accepts bare UUIDs during the migration period.
ADR-0010 created. ✅ 2026-03-10

### ❌ `vultron/enums.py` backward-compat shim still present (TECHDEBT-4)

`activity_patterns.py` and `semantic_map.py` have been deleted (ARCH-CLEANUP-1).
`vultron/enums.py` remains as a backward-compat re-export shim for `MessageSemantics`
plus defines `OfferStatusEnum` and `VultronObjectType`. These two domain-boundary
enums should eventually be relocated (`OfferStatusEnum` → `core/models/`,
`VultronObjectType` → `wire/as2/enums.py` or `core/models/`). `vultron/enums.py`
can then be deleted. Low priority; depends on completing PRIORITY-60 and PRIORITY-70.

### ❌ Multi-actor demos not yet started (PRIORITY 300)

Blocked by PRIORITY-100 and PRIORITY-200.

---

## Prioritized Task List

### Phase PRIORITY-30 — Triggerable Behaviors (COMPLETE ✅)

All P30 tasks (P30-1 through P30-6) complete. All 9 trigger endpoints implemented.
See `plan/IMPLEMENTATION_HISTORY.md` for details.

---

### Phase PRIORITY-50 — Hexagonal Architecture (COMPLETE with regressions ⚠️)

P50-0 and ARCH-1.1 through ARCH-1.4 complete. V-01 through V-12 formally
remediated. However, V-02-R, V-03-R, V-10-R, V-11-R are **active regressions**
and V-13 through V-23 are **new violations** introduced by P60-2.
All are addressed in Phase PRIORITY-65 below.
See `plan/IMPLEMENTATION_HISTORY.md` for P50/ARCH-CLEANUP task details.

---

### Phase PRIORITY-60 — Continue Hexagonal Architecture Refactor (COMPLETE ✅)

P60-1 (`as_vocab/` → `wire/as2/vocab/`), P60-2 (`behaviors/` →
`core/behaviors/`), P60-3 (`adapters/` package stub) all complete.
TECHDEBT-11 (test layout) complete. See `plan/IMPLEMENTATION_HISTORY.md` for details.

---

### Phase SPEC-COMPLIANCE-3 — Embargo Acceptance Tracking (COMPLETE ✅)

SC-PRE-2, SC-3.2, SC-3.3 all complete. See `plan/IMPLEMENTATION_HISTORY.md`.

---

### Technical Debt (housekeeping) — all complete ✅

TECHDEBT-3, TECHDEBT-7, TECHDEBT-8, TECHDEBT-9, TECHDEBT-10, TECHDEBT-11,
TECHDEBT-12 all done. TECHDEBT-4 superseded. See `plan/IMPLEMENTATION_HISTORY.md`.

---

### Phase PRIORITY-65 — Address Architecture Violations

**Reference**: `plan/PRIORITIES.md` PRIORITY 65, `notes/architecture-review.md`
V-02-R, V-03-R, V-10-R, V-11-R, V-13 through V-23; R-07 through R-11

**Note**: P65-1 replaces P70-1 (same work). P65-1 through P65-5 and P65-6a
are complete. Remaining work: P65-6b → P65-7 (in dependency order).

Work in dependency order: P65-1 and P65-2 are independent (both done); P65-3
is the largest task (done); P65-4 depends on P65-3 (done); P65-5 requires
P65-1 (done); P65-6a requires P65-3 (done); P65-6b requires P65-5 and P65-6a;
P65-7 closes out the test regressions last (requires P65-4, P65-6a, and P65-6b).

- [x] **P65-1** (R-08): Move `DataLayer` Protocol from
  `vultron/api/v2/datalayer/abc.py` to `vultron/core/ports/activity_store.py`.
  Update `core/behaviors/bridge.py` and `core/behaviors/helpers.py` to import
  `DataLayer` from `core/ports/`. Remove the `Record` import from
  `core/behaviors/helpers.py` — BT nodes must pass domain Pydantic models to the
  port, not adapter record types. The `TinyDbDataLayer` stays in `api/v2/datalayer/`
  and imports from `core/ports/`. Provide a backward-compat re-export at the old
  location, then remove once all callers are updated. Done when `core/ports/
  activity_store.py` contains the Protocol, no core module imports `DataLayer`
  from `api/v2/`, and tests pass. Addresses V-13, V-14.

- [x] **P65-2** (R-11): Fix module-level DataLayer instantiation in
  `vultron/api/v2/backend/inbox_handler.py`. Replace module-level
  `DISPATCHER = get_dispatcher(..., dl=get_datalayer())` with a FastAPI lifespan
  event or app-factory pattern that injects the `DataLayer` once at startup.
  Remove the per-call `DISPATCHER.dl = get_datalayer()` mutation. Remove the
  `handler_map=None` default from `DispatcherBase.__init__()` (require explicit
  injection). Done when no `get_datalayer()` call appears at module level or
  inside `dispatch()`, and tests pass. Addresses V-10-R, V-20.

- [x] **P65-3** (R-07): Enrich `InboundPayload`; eliminate `raw_activity`. Steps
  completed: (1) Audited all handler files for `raw_activity` field accesses.
  (2) Added 13 typed domain string fields to `InboundPayload` in
  `core/models/events.py` (activity_type, target_id/type, context_id/type,
  origin_id/type, inner_object/target/context id/type). (3) Added
  `extract_intent()` to `wire/as2/extractor.py` returning
  `(MessageSemantics, InboundPayload)` with all fields populated from the AS2
  object graph. (4) Added `wire_activity: Any` and `wire_object: Any` to
  `DispatchActivity` (adapter-layer) for handler persistence; handlers read
  domain data from `payload` and use these for AS2 object storage only.
  (5) Updated all 7 handler files to read exclusively from `InboundPayload`
  fields — no `raw_activity` references remain. (6) Removed `.model_dump_json()`
  call on raw activity from `dispatch()`. Addresses V-02-R, V-11-R, V-21.

- [x] **P65-4** (R-10): Decouple `behavior_dispatcher.py` from the wire layer.
  Move the `extract_intent()` call (currently in `prepare_for_dispatch` at
  `behavior_dispatcher.py` line 27) upstream into the adapter-layer inbox handler
  (`vultron/api/v2/backend/inbox_handler.py`), which should call `extract_intent()`
  directly and construct a fully-populated `DispatchActivity` before passing it
  to the dispatcher. Remove `from vultron.wire.as2.extractor import
  find_matching_semantics, extract_intent` from `behavior_dispatcher.py`.
  Remove or relocate `prepare_for_dispatch()` to the adapter layer
  (`inbox_handler.py` or a new `adapters/driving/` module). Done when
  `behavior_dispatcher.py` contains no wire-layer imports, and tests pass.
  Addresses V-03-R. **Depends on P65-3 (done).**

  Note: V-20 (lazy handler map import) and V-21 (`.model_dump_json()` on
  `raw_activity`) were resolved as side effects of P65-2 and P65-3
  respectively. P65-4 scope is now V-03-R only.

- [x] **P65-5** (R-09 part 1): Remove adapter-layer persistence calls from core
  BT nodes. In `core/behaviors/report/nodes.py` and
  `core/behaviors/case/nodes.py`, replace all `object_to_record(obj)` +
  `dl.update(id, record)` patterns with direct `dl.update(id, obj.model_dump())`
  or a thin `save(dl, obj)` helper defined in `core/ports/` (not in the adapter).
  Remove imports of `object_to_record` and `OfferStatus` from these files.
  Remove the lazy imports at `nodes.py` lines 744–745. Done when no core BT
  module imports from `api/v2/datalayer/db_record` or `api/v2/data/status`,
  and tests pass. Addresses V-14 (Record), V-15 partial, V-16, V-18 partial.
  **Depends on P65-1.**

- [x] **P65-6a**: Define `VultronEvent` base class and per-semantic inbound
  domain event subclasses in `core/models/events/`. Converted `events.py`
  to a package (`events/`) with `base.py` (VultronEvent + MessageSemantics),
  category submodules (`report.py`, `case.py`, `actor.py`, `case_participant.py`,
  `embargo.py`, `note.py`, `status.py`, `unknown.py`) each containing
  `FooReceivedEvent` classes with `semantic_type: Literal[...]` discriminators,
  `__init__.py` exporting all types plus `EVENT_CLASS_MAP` and backward-compat
  `InboundPayload = VultronEvent` alias. Updated `extract_intent()` to return
  the concrete typed subclass (not a tuple). Updated `DispatchActivity.payload`
  type to `VultronEvent`. Removed redundant `object_type` string guards from
  `create_report`, `submit_report`, and `validate_report` handlers. Updated
  `inbox_handler.py`, `test_behavior_dispatcher.py`, `test_handlers.py`, and
  `test_reporting_workflow.py` to use the new API. 880 tests pass.
  **Depends on P65-3 (done).** See `notes/domain-model-separation.md`.

- [x] **P65-6b** (R-09 part 2): Replace AS2 wire types in core BT nodes and
  policy with domain types. Using the outbound-event domain types defined in
  P65-6a (or new `FooTriggerEvent` types in `core/models/events/`), replace
  direct construction of `CreateCase`, `VulnerabilityCase`, `CaseActor`,
  `VendorParticipant` inside `core/behaviors/case/nodes.py` and
  `core/behaviors/report/nodes.py`. Add an outbound serializer in
  `wire/as2/serializer.py` that converts domain events to AS2 wire format
  (used by adapter layer, not core). Update `core/behaviors/report/policy.py`
  method signatures to take domain Pydantic types instead of
  `VulnerabilityCase`/`VulnerabilityReport` wire types. Update
  `core/behaviors/case/create_tree.py` factory to accept domain types.
  Done when no `core/behaviors/` module imports from `wire/as2/vocab/`, and
  tests pass. Addresses V-15 full, V-17, V-18 full, V-19.
  **Depends on P65-5 (done), P65-6a.**

- [x] **P65-7**: Fix test regressions. Update
  `test/test_behavior_dispatcher.py` to remove the `as_Create` wire import —
  the `prepare_for_dispatch` test will move to the adapter layer with P65-4.
  Update `test/core/behaviors/report/test_nodes.py`,
  `test/core/behaviors/report/test_prioritize_tree.py`,
  `test/core/behaviors/report/test_validate_tree.py`,
  `test/core/behaviors/case/test_create_tree.py`, and
  `test/core/behaviors/test_performance.py` to use domain objects as fixtures
  rather than AS2 wire types (`as_Offer`, `VulnerabilityReport`, `as_Service`,
  `VulnerabilityCase`, `as_Accept`). Done when no core test imports wire-layer
  AS2 types, and tests pass. Addresses V-22, V-23.
  **Depends on P65-4, P65-6a, and P65-6b.**

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

**Blocked by**: P65 (P65-1 is P70-1; complete P65 first).
**Must precede**: PRIORITY-100 (actor independence uses the new layer structure).

- ~~[ ] **P70-1**~~ **SUPERSEDED by P65-1** — DataLayer Protocol move to
  `core/ports/` is handled there.

- [ ] **P70-2**: Move `OfferStatusEnum` and `VultronObjectType` from
  `vultron/enums.py` to their correct architectural homes (`core/models/` and
  `wire/as2/enums.py` respectively). Delete `vultron/enums.py`. Done when no
  `vultron.enums` imports remain and tests pass.

- [ ] **P70-3**: Stub `vultron/core/ports/` with `delivery_queue.py` and
  `dns_resolver.py` Protocol interfaces (matching the target layout in
  `notes/architecture-ports-and-adapters.md`). No logic required. Done when
  `core/ports/__init__.py` and the two stub files are committed.

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
