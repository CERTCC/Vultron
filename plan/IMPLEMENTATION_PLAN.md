# Vultron API v2 Implementation Plan

**Last Updated**: 2026-03-10 (P60-2 complete: vultron/behaviors/ moved to vultron/core/behaviors/)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Completed phase history is in `plan/IMPLEMENTATION_HISTORY.md`.

### Current Status Summary

**Test suite**: 822 passing, 5581 subtests, 0 xfailed (2026-03-10, after P60-1)

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

## Gap Analysis (2026-03-10, refresh #21)

### ✅ Previously completed (see `plan/IMPLEMENTATION_HISTORY.md`)

BUGFIX-1, REFACTOR-1, DEMO-3, DEMO-4, SPEC-COMPLIANCE-1, SPEC-COMPLIANCE-2,
SC-3.1, SC-PRE-1, TECHDEBT-1, TECHDEBT-5, TECHDEBT-6, P30-1, P30-2, P30-3,
P30-4, P30-5, P30-6, P50-0, ARCH-1.1, ARCH-1.2, ARCH-1.3, ARCH-1.4.

### ❌ Outbox delivery not implemented (lower priority)

`actor_io.py` stub logs placeholder messages (OX-03-001, OX-04-001, OX-04-002).

### ✅ Triggerable behaviors fully implemented (PRIORITY 30 — COMPLETE)

All 9 trigger endpoints in split router files. P30-1 through P30-6 complete.

### ✅ Hexagonal architecture Phase 1 complete (PRIORITY 50 — COMPLETE)

P50-0 through ARCH-1.4 complete. V-01 through V-10 remediated.
Backward-compat shims remain for `activity_patterns.py`, `semantic_map.py`,
`semantic_handler_map.py` — one test still imports from the shim. AS2 structural
enums (`as_ObjectType`, `as_TransitiveActivityType`, etc.) still live in
`vultron/enums.py` rather than `vultron/wire/as2/enums.py`.
V-11 (`isinstance` on AS2 types in handler bodies) and V-12 (dispatcher test uses
AS2 types) are not yet remediated. No ADR for the hexagonal architecture decision
has been written.

### ❌ ARCH cleanup items (PRIORITY 50 follow-on — immediate)

Four discrete cleanup tasks remain after P50: delete shims, move AS2 structural
enums to the wire layer, fix V-11/V-12, write the architecture ADR
(see Phase ARCH-CLEANUP below).

### ❌ Package relocation not started (PRIORITY 60 — next after cleanup)

`vultron/as_vocab/` (wire vocabulary), `vultron/behaviors/` (BT/domain logic), and
`vultron/enums.py` (mixed domain + wire enums) need to be relocated into the
`wire/` and `core/` packages per `plan/PRIORITIES.md` PRIORITY 60 and
`notes/architecture-ports-and-adapters.md`.

### ❌ Actor independence not implemented (PRIORITY 100)

All actors share a singleton `TinyDbDataLayer` instance. PRIORITY 100 requires
per-actor isolated state. Options documented in `notes/domain-model-separation.md`
(Option B: TinyDB namespace prefix; MongoDB community edition for production).

### ❌ CaseActor broadcast not implemented (PRIORITY 200)

CM-06-001 requires CaseActor to notify all case participants on case state update.
Blocked by OUTBOX-1.

### ⚠️ SPEC-COMPLIANCE-3 partially done (SC-PRE-2, SC-3.2, SC-3.3 remain)

`add_participant()` on `VulnerabilityCase` exists but does not maintain an
`actor_participant_index` dict (SC-PRE-2 incomplete). No handler records embargo
acceptances with trusted timestamps (SC-3.2). No `update_case` guard checks
participant embargo acceptance (SC-3.3).

### ❌ CS-08-001 — Optional string fields allow empty strings (TECHDEBT-7/9)

No Pydantic validators enforce "if present, then non-empty" on `Optional[str]`
fields across `vultron/as_vocab/objects/` models.

### ❌ Pyright static type checking not configured (TECHDEBT-8)

No `pyrightconfig.json` exists. `specs/tech-stack.md` IMPL-TS-07-002 requires
pyright adoption with a gradual approach.

### ❌ Object IDs not standardized to URL-like form (TECHDEBT-3)

No ADR for `docs/adr/ADR-XXXX-standardize-object-ids.md`. `specs/object-ids.md`
OID-01 through OID-04 defines requirements.

### ❌ Multi-actor demos not yet started (PRIORITY 300)

Blocked by PRIORITY-100 and PRIORITY-200.

---

## Prioritized Task List

### Phase PRIORITY-30 — Triggerable Behaviors (COMPLETE)

**Reference**: `specs/triggerable-behaviors.md`, `notes/triggerable-behaviors.md`

All P30 tasks complete (P30-1 through P30-6). All 9 trigger endpoints implemented.
See `plan/IMPLEMENTATION_HISTORY.md` for details.

---

### Phase PRIORITY-50 — Hexagonal Architecture Starting with `triggers.py` (COMPLETE)

**Reference**: `plan/PRIORITIES.md` PRIORITY 50, `specs/architecture.md`,
`notes/architecture-review.md` V-01 to V-11, R-01 to R-06

All P50 tasks complete. V-01 through V-10 remediated. See
`plan/IMPLEMENTATION_HISTORY.md` for details.

- [x] **P50-0**: Extract domain service layer from `triggers.py`; split into three
  focused router modules (`trigger_report.py`, `trigger_case.py`,
  `trigger_embargo.py`) and a `trigger_services/` backend package.
- [x] **ARCH-1.1** (R-01): `MessageSemantics` moved to `vultron/core/models/events.py`.
- [x] **ARCH-1.2** (R-02): `InboundPayload` domain type introduced; AS2 type removed
  from `DispatchActivity.payload`.
- [x] **ARCH-1.3** (R-03 + R-04): `wire/as2/parser.py` and `wire/as2/extractor.py`
  created; parsing and extraction consolidated; shims left for compatibility.
- [x] **ARCH-1.4** (R-05 + R-06): DataLayer injected via port; handler map moved to
  adapter layer (`vultron/api/v2/backend/handler_map.py`).

---

### Phase ARCH-CLEANUP — PRIORITY 50 Follow-on Cleanup (immediate)

**Reference**: `notes/architecture-review.md` V-11, V-12; `docs/adr/_adr-template.md`

Four discrete cleanup tasks complete the PRIORITY-50 work. Work in order.

- [x] **ARCH-CLEANUP-1**: Delete backward-compat shims `vultron/activity_patterns.py`,
  `vultron/semantic_map.py`, and `vultron/semantic_handler_map.py`. Update the one
  remaining caller (`test/api/test_reporting_workflow.py:36`) to import
  `find_matching_semantics` from `vultron.wire.as2.extractor` directly. Done when
  shim files are gone and tests pass.

- [x] **ARCH-CLEANUP-2**: Move AS2 structural enums (`as_ObjectType`, `as_ActorType`,
  `as_IntransitiveActivityType`, `as_TransitiveActivityType`, `merge_enums`,
  `as_ActivityType`, `as_AllObjectTypes`) from `vultron/enums.py` to a new
  `vultron/wire/as2/enums.py` module. Update the four `as_vocab/base/objects/`
  files that import these enums. Reduce `vultron/enums.py` to only `OfferStatusEnum`
  and `VultronObjectType` (plus the `MessageSemantics` re-export). Done when no
  AS2 structural enums remain in `vultron/enums.py` and tests pass.

- [x] **ARCH-CLEANUP-3**: Replace `isinstance(x, AS2Type)` checks in handler files
  (`vultron/api/v2/backend/handlers/report.py`, `handlers/case.py`) and trigger
  services (`trigger_services/report.py`, `trigger_services/_helpers.py`) with
  `InboundPayload.object_type` string comparisons (V-11). Update
  `test/test_behavior_dispatcher.py` to construct `InboundPayload` directly using
  domain types rather than `as_Create`/`as_Activity` objects (V-12). Done when no
  `isinstance` checks against AS2 types remain in handler/service code and
  tests pass.

- [x] **ARCH-ADR-9**: Write `docs/adr/0009-hexagonal-architecture.md` documenting
  the decision to adopt hexagonal architecture for Vultron. Reference
  `notes/architecture-ports-and-adapters.md`, `notes/architecture-review.md`,
  `specs/architecture.md`. Record violations V-01 through V-12, what was remediated
  (ARCH-1.1 through ARCH-1.4), and what remains (ARCH-CLEANUP, PRIORITY-60
  package relocation). Done when ADR is committed and indexed in `docs/adr/index.md`.

---

### Phase PRIORITY-60 — Continue Hexagonal Architecture Refactor

**Reference**: `plan/PRIORITIES.md` PRIORITY 60, `notes/architecture-ports-and-adapters.md`

The goal is to relocate packages into the `wire/`, `core/`, and `adapters/`
layer structure defined in `notes/architecture-ports-and-adapters.md`. Work
incrementally — each task must leave tests passing.

- [x] **P60-1**: Move `vultron/as_vocab/` into the wire layer. Relocate
  `vultron/as_vocab/` to `vultron/wire/as2/vocab/` (keeping base types, objects,
  activities, and examples sub-packages). Provide a backward-compat shim at
  `vultron/as_vocab/` re-exporting from the new location. Update all direct
  imports in `vultron/behaviors/`, `vultron/api/`, `test/`, and `vultron/demo/`.
  Remove the shim once all callers are updated. Done when `vultron/as_vocab/` is
  gone and tests pass.

- [x] **P60-2**: Move `vultron/behaviors/` to `vultron/core/behaviors/`. Relocate
  all BT bridge, helper, and tree modules. Provide a compatibility shim at
  `vultron/behaviors/` then remove once all callers are updated. Done when
  `vultron/behaviors/` is gone and tests pass.

- [ ] **P60-3**: Stub the `vultron/adapters/` package per the target layout in
  `notes/architecture-ports-and-adapters.md`. Create `vultron/adapters/driving/`
  with placeholder `cli.py`, `http_inbox.py`, `mcp_server.py`; create
  `vultron/adapters/driven/` with placeholder `activity_store.py`,
  `delivery_queue.py`, `http_delivery.py`; create
  `vultron/adapters/connectors/base.py` with `ConnectorPlugin` Protocol stub.
  No logic required — stubs establish the package structure and document intent.
  Done when the directory tree exists, `__init__.py` files are in place, and
  no existing tests break.

---

### Phase SPEC-COMPLIANCE-3 — Embargo Acceptance Tracking + Trusted Timestamps

**Reference**: `specs/case-management.md` CM-10, CM-02-009

- [ ] **SC-PRE-2**: Add `actor_participant_index: dict[str, str]` field to
  `VulnerabilityCase`; update `add_participant()` and add `remove_participant()`
  to maintain the index atomically (CM-10-002). Update all handlers that create or
  remove participants to use these methods. Add tests confirming index consistency.

- [ ] **SC-3.2**: In `accept_invite_to_embargo_on_case` and
  `accept_invite_actor_to_case` handlers, record the accepted embargo ID in
  `CaseParticipant.accepted_embargo_ids` using the CaseActor's trusted timestamp
  via `VulnerabilityCase.record_event()` (CM-10-002, CM-02-009). Add tests.

- [ ] **SC-3.3**: Add a guard in `update_case` (or a shared helper) that checks
  each active participant has accepted the current embargo before broadcasting
  (CM-10-004). For prototype: log WARNING when a participant has not accepted;
  full enforcement is PRIORITY-200. Add unit tests.

---

### Technical Debt (housekeeping)

- [ ] **TECHDEBT-9**: Introduce `NonEmptyString` and `OptionalNonEmptyString` type
  aliases in `vultron/as_vocab/base/` (CS-08-001, CS-08-002). Replace existing
  per-field empty-string validators with the shared type. **Combine with
  TECHDEBT-7** in one agent cycle.

- [ ] **TECHDEBT-7**: Add Pydantic validators rejecting empty strings in all
  remaining `Optional[str]` fields across `vultron/as_vocab/objects/` models
  (CS-08-001). Done when all fields reject empty strings and tests pass.

- [ ] **TECHDEBT-10**: Backfill pre-case events into the case event log at case
  creation (CM-02-009). `create_case` BT SHOULD call `record_event()` for the
  originating Offer receipt and case creation events. Add tests.

- [ ] **TECHDEBT-8**: Configure pyright for gradual static type checking
  (IMPL-TS-07-002). Commit `pyrightconfig.json` at `basic` strictness; run
  pyright to produce a baseline error count documented in
  `plan/IMPLEMENTATION_NOTES.md`; add a `Makefile` target. Done when config
  committed and baseline documented.

- [ ] **TECHDEBT-3**: Standardize object IDs to URL-like form — draft ADR
  `docs/adr/ADR-XXXX-standardize-object-ids.md` and implement a compatibility
  shim in the DataLayer (OID-01 through OID-04). Done when ADR created and
  tests validate URL-like ID acceptance.

- [ ] **TECHDEBT-4**: Reorganize top-level modules (`activity_patterns`,
  `semantic_map`, `enums`) into small packages to reduce circular imports and
  improve discoverability. Done when modules moved with minimal interface
  changes and tests pass.

  **Note**: TECHDEBT-4 overlaps with ARCH-1.1/ARCH-1.3; defer until those tasks
  are complete or tackle as part of them.

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

### Phase PRIORITY-100 — Actor Independence (PRIORITY 100)

**Reference**: `plan/PRIORITIES.md` PRIORITY 100,
`specs/case-management.md` CM-01,
`notes/domain-model-separation.md` (Per-Actor DataLayer Isolation Options)

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
