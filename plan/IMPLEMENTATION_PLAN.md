# Vultron API v2 Implementation Plan

**Last Updated**: 2026-02-27 (gap analysis refresh #10)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Completed phase history is in `plan/IMPLEMENTATION_HISTORY.md`.

### Current Status Summary

**Test suite**: 568 passing, 5581 subtests, 0 xfailed (2026-02-26)

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

**Demo scripts** (all dockerized in `docker-compose.yml`):
`receive_report_demo.py`, `initialize_case_demo.py`, `invite_actor_demo.py`,
`establish_embargo_demo.py`, `status_updates_demo.py`, `suggest_actor_demo.py`,
`transfer_ownership_demo.py`, `acknowledge_demo.py`, `manage_case_demo.py`,
`initialize_participant_demo.py`, `manage_embargo_demo.py`,
`manage_participants_demo.py`

---

## Gap Analysis (2026-02-27, refresh #10)

### ✅ Phase DEMO-3 fully complete

All 15 tasks (DEMO-3.1–3.15) are done. All demo scripts exist in
`vultron/demo/`, tests exist in `test/demo/`, and Docker services exist
in `docker/docker-compose.yml`.

### ✅ Phase DEMO-4 fully complete

All 19 tasks (DEMO-4.1–4.19) are done. See `plan/IMPLEMENTATION_HISTORY.md`
for the full record.

### ❌ CM-03-006 field rename not implemented

`VulnerabilityCase.case_status` is a `list[CaseStatusRef]` (history) but
named in the singular; spec requires `case_statuses`. Same for
`CaseParticipant.participant_status`.

### ❌ Outbox delivery not implemented (lower priority)

`actor_io.py` stub logs placeholder messages instead of writing to recipient
actor inboxes (OX-03-001, OX-04-001, OX-04-002).

### ❌ Triggerable behaviors not designed/implemented (PRIORITY 30)

PRIORITIES.md PRIORITY 30 calls for exposing behaviors the local actor can
initiate based on internal state, not just reactive message processing.
The behavior tree docs exist (`docs/topics/behavior_logic/rm_bt.md`,
`rm_validation_bt.md`, `rm_prioritization_bt.md`, `rm_closure_bt.md`,
`em_bt.md`, `em_eval_bt.md`, `em_propose_bt.md`) but no API trigger
endpoints are implemented. Design work is needed before implementation.

### ❌ Actor independence not implemented (PRIORITY 100)

All actors share a singleton `TinyDbDataLayer` instance. PRIORITIES.md
Priority 100 requires each actor to have an isolated BT execution domain
with no shared blackboard state. The current design does not prevent
actors from seeing each other's state.

### ❌ CaseActor broadcast not implemented (PRIORITY 200)

`CM-06-001` requires CaseActor to notify all current case participants when
canonical case state is updated. This depends on outbox delivery (OUTBOX-1)
and is blocked until that lands.

### ❌ CM-05 domain object types missing

`VulnerabilityRecord` and `Publication` Pydantic model types specified in
CM-05-001 do not exist in the codebase. `specs/case-management.md` CM-05-002
through CM-05-007 cover their lifecycle constraints.

### ❌ CM-02-008 vendor initial participant not verified in create_case BT

`specs/case-management.md` CM-02-008 requires the vendor/coordinator to be
recorded as the initial primary participant when a case is created from a
`VulnerabilityReport` Offer. The `create_case` BT (`vultron/behaviors/case/
create_tree.py`) does not visibly create a `VendorParticipant` before adding
other participants.

### ❌ Embargo policy model not implemented (EP-01-001 to EP-01-004)

`specs/embargo-policy.md` EP-01 specifies a structured `EmbargoPolicy` Pydantic
model. No `EmbargoPolicy` class exists in the codebase. The API endpoint and
compatibility evaluation (EP-02, EP-03) are `PROD_ONLY` but the model itself
is not tagged `PROD_ONLY` and should be added.

### ❌ Pytest logging noise from app.py root logger side effect

`vultron/api/v2/app.py` calls `logging.getLogger().setLevel(logging.DEBUG)`
and reassigns root logger handlers at module import time. This pollutes pytest
output with `ValueError: I/O operation on closed file.` errors from closed
stream handlers after tests tear down. See `plan/BUGS.md` for details.

### ❌ Spurious print statements in test files

`test/behaviors/test_performance.py`, `test/bt/test_case_states/test_conditions.py`,
`test/as_vocab/test_vulnerability_report.py`, and `test/as_vocab/
test_create_activity.py` contain `print()` calls that pollute test output.
See `plan/BUGS.md` for details.

### ❌ AR-01-003 — missing unique `operation_id` on FastAPI routes

No `operation_id` kwargs are set on any FastAPI route decorator; FastAPI
auto-generates them from function names which may not be stable or unique
across router boundaries.

---

## Prioritized Task List

### Phase DEMO-3 — Remaining ActivityPub Workflow Demo Scripts

**Status**: ✅ COMPLETE — See `plan/IMPLEMENTATION_HISTORY.md`

---

### Phase DEMO-4 — Unified Demo CLI

**Status**: ✅ COMPLETE — See `plan/IMPLEMENTATION_HISTORY.md`

---

### Phase BUGFIX-1 — Pytest Logging Noise (Priority: HIGH — developer quality of life)

**Reference**: `plan/BUGS.md`, `notes/codebase-structure.md`

- [x] **BUGFIX-1.1**: Move root-logger configuration out of module-level code
  in `vultron/api/v2/app.py` — use `lifespan` event or lazy init so that
  importing `app.py` in tests does not mutate the root logger's handlers or
  level. Confirm no `--- Logging error ---` noise in `uv run pytest` output.
- [x] **BUGFIX-1.2**: Replace `print()` calls in
  `test/behaviors/test_performance.py`, `test/bt/test_case_states/
  test_conditions.py`, `test/as_vocab/test_vulnerability_report.py`, and
  `test/as_vocab/test_create_activity.py` with proper logging or
  pytest-compatible assertions. Confirm no spurious stdout output in
  `uv run pytest -s` output.

---

### Phase REFACTOR-1 — CM-03-006: Status History Field Renames (Priority: MEDIUM)

**Priority**: MEDIUM — improves spec compliance; touches many files
**Reference**: `specs/case-management.md` CM-03-006

- [ ] **REFACTOR-1.1**: Rename `VulnerabilityCase.case_status` (list) →
  `case_statuses`; add `case_status` as read-only property returning
  `current_status` (most recent by timestamp)
  - Update `vulnerability_case.py`, all references in `handlers.py`,
    `behaviors/`, and tests
- [ ] **REFACTOR-1.2**: Rename `CaseParticipant.participant_status` (list) →
  `participant_statuses`; add `participant_status` as read-only property
  - Update `case_participant.py`, all references in `handlers.py` and tests
- [ ] **REFACTOR-1.3**: Run full test suite; fix all breakage; confirm 0 regressions

---

## Technical debt (housekeeping)

Priority: TECHDEBT-1 and TECHDEBT-5 are MEDIUM per `plan/PRIORITIES.md`
(PRIORITY 20). TECHDEBT-2 is subsumed into DEMO-4 above. TECHDEBT-3 and
TECHDEBT-4 remain LOW.

- [x] TECHDEBT-2: Subsumed into Phase DEMO-4 (DEMO-4.1–4.3).

- [x] TECHDEBT-1: Split large handlers module into submodules — move related
  handlers into `vultron/api/v2/backend/handlers/*.py` and re-export in
  `vultron.api.v2.backend.handlers.__init__`.
  Done when: handlers module size reduces below 400 LOC and full test-suite passes.
  **Completed**: handlers/ package with 8 submodules; __init__.py ~100 lines; 592 tests pass.

- [x] TECHDEBT-5: Move `vultron/scripts/vocab_examples.py` to
  `vultron/as_vocab/examples/` and provide a compatibility shim for existing
  import paths.
  Done when: new location is used and existing import paths remain 
  functional and module has been split if needed to reduce size below 400 
  LOC. Note previous work moved the file but did not split it. Similar to 
  TECHDEBT-1, re-export all public names from `vultron/as_vocab/examples/__init__.py`
  and modify the `scripts/vocab_examples.py` to import from there so that the 
  old import path still works.
  **Completed**: Split into 8 submodules (_base, actor, case, embargo, note,
  participant, report, status) mirroring handlers structure; vocab_examples.py
  is now 312 LOC (main() + re-exports); all submodules under 230 LOC.
  592 tests pass.

- [ ] TECHDEBT-3: Standardize object IDs to URL-like form — draft ADR
  `docs/adr/ADR-XXXX-standardize-object-ids.md` and implement a compatibility
  shim in the DataLayer that accepts existing IDs.
  Done when: ADR created and tests validate URL-like ID acceptance.

- [ ] TECHDEBT-4: Reorganize top-level modules (activity_patterns, semantic_map,
  enums) into small packages to reduce circular imports and improve
  discoverability.
  Done when: modules moved with minimal interface changes and tests pass.

References: `notes/codebase-structure.md`, `plan/IMPLEMENTATION_NOTES.md`,
`plan/IDEATION.md`, and files in `specs/`.

---

### Phase SPEC-COMPLIANCE-1 — Object Model Gaps (Priority: MEDIUM)

**Reference**: `specs/case-management.md` CM-05-*, CM-02-008

- [ ] **SC-1.1**: Add `VulnerabilityRecord` Pydantic model (CM-05-001)
  — persistent identifier record (e.g., CVE number) with `name`, `url`,
  `case_id` fields. Add to `vultron/as_vocab/objects/`. Add unit tests.
- [ ] **SC-1.2**: Add `Publication` Pydantic model (CM-05-001, CM-05-005)
  — reference-link record with `title`, `publisher`, `date`, `url` fields;
  no embedded content. Add to `vultron/as_vocab/objects/`. Add unit tests.
- [ ] **SC-1.3**: Verify `create_case` BT records vendor as initial
  `CaseParticipant` before other participants (CM-02-008); add test asserting
  vendor `attributed_to` is set on case at creation.

---

### Phase SPEC-COMPLIANCE-2 — Embargo Policy Model (Priority: MEDIUM)

**Reference**: `specs/embargo-policy.md` EP-01

- [ ] **EP-1.1**: Add `EmbargoPolicy` Pydantic model (EP-01-001 to EP-01-004)
  with `actor_id`, `inbox`, `preferred_duration_days`,
  `minimum_duration_days`, `maximum_duration_days`, `notes` fields.
  Add to `vultron/as_vocab/objects/embargo_policy.py`. Add unit tests.
- [ ] **EP-1.2**: Add `embargo_policy` optional field to `VultronActor` (or
  equivalent actor profile model) referencing the `EmbargoPolicy` record.

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

### Phase PRIORITY-30 — Triggerable Behaviors (PRIORITY 30)

**Reference**: `plan/PRIORITIES.md` PRIORITY 30, `docs/topics/behavior_logic/`

Design and implementation of API-level trigger endpoints for behaviors the
local actor initiates based on internal state (not purely reactive to messages).
Candidate behaviors (from `docs/topics/behavior_logic/`):

- RM behaviors: validate report, engage/defer case, close report
- EM behaviors: propose/evaluate embargo, terminate embargo
- Actor-initiated: publish vulnerability, assign ID

- [ ] **P30-1**: Design triggerable behavior API — draft ADR or design note
  documenting endpoint shape (`POST /actors/{actor_id}/trigger/{behavior}`),
  input schema, response format, and which behaviors are in scope.
  Reference `docs/topics/behavior_logic/` behavior docs and
  `specs/behavior-tree-integration.md` BT-08 (CLI MAY).
- [ ] **P30-2**: Implement `POST /actors/{actor_id}/trigger/validate-report`
  endpoint that invokes the `validate_report` BT on a named report.
- [ ] **P30-3**: Implement `POST /actors/{actor_id}/trigger/engage-case`
  endpoint that invokes the `engage_case` BT.
- [ ] **P30-4**: Implement `POST /actors/{actor_id}/trigger/defer-case`
  endpoint that invokes the `defer_case` BT.
- [ ] **P30-5**: Implement remaining EM trigger endpoints based on design
  from P30-1 (propose embargo, terminate embargo).
- [ ] **P30-6**: Add tests for each trigger endpoint; update `vultron-demo`
  CLI to include a demo exercising at least one trigger endpoint.

---

### Phase PRIORITY-100 — Actor Independence (PRIORITY 100)

**Reference**: `plan/PRIORITIES.md` PRIORITY 100,
`specs/behavior-tree-integration.md` BT-09,
`specs/case-management.md` CM-01

Actors currently share a singleton DataLayer. Actor independence requires
each actor to have an isolated state domain. This is significant
architectural work; a design step is required first.

- [ ] **ACT-1**: Draft design note or ADR for per-actor DataLayer isolation —
  identify options (per-actor TinyDB file, namespace prefix, separate
  singleton per `actor_id`), trade-offs, and migration path from shared
  singleton. Consult `notes/domain-model-separation.md`.
- [ ] **ACT-2**: Implement per-actor DataLayer isolation per chosen design.
  Done when: Actor A's DataLayer operations do not affect Actor B's state;
  tests confirm isolation.
- [ ] **ACT-3**: Update `get_datalayer` dependency and all handler tests to
  use per-actor DataLayer fixtures.

---

### Phase PRIORITY-200 — CaseActor Broadcast (PRIORITY 200)

**Blocked by**: OUTBOX-1 (requires outbox delivery)
**Reference**: `plan/PRIORITIES.md` PRIORITY 200,
`specs/case-management.md` CM-06

- [ ] **CA-1**: After OUTBOX-1 is complete, implement CaseActor broadcast
  in `update_case` handler — after updating canonical case state, send
  an ActivityStreams activity to each active `CaseParticipant`'s inbox
  (CM-06-001, CM-06-002).
- [ ] **CA-2**: Add `GET /actors/{case_actor_id}/action-rules` endpoint
  returning valid CVD actions for a named participant given current
  RM/EM/CS/VFD state (CM-07-001, AR-07-001, AR-07-002). Add tests.
- [ ] **CA-3**: Add tests verifying CaseActor notifies all participants on
  case state update.

---

## Deferred (Per PRIORITIES.md)

The following are deferred until higher-priority phases are complete:

- **Production readiness** (Phase 1–3): Request validation, error responses,
  health check readiness probe, structured logging, idempotency/duplicate detection,
  test coverage enforcement — all `PROD_ONLY` or low-priority
- **Response generation** (Phase 5): Accept/Reject/TentativeReject response builders,
  outbox delivery with retry/backoff — see historical task list in
  `IMPLEMENTATION_HISTORY.md`
- **Code quality** (Phase 6): `mypy`, `black` audit, docstring coverage
- **Performance / scalability** (Phase 7): Queue-based dispatcher, DB replacement,
  rate limiting
- **EP-02/EP-03**: EmbargoPolicy API endpoint and compatibility evaluation
  (`PROD_ONLY`)
- **AR-01-003**: Unique `operation_id` on all FastAPI routes (LOW, pre-production)
- **AR-04/AR-05/AR-06**: Long-running job tracking, pagination, bulk ops
  (all `PROD_ONLY`)
- **Domain model separation** (CM-08): Decouple wire/domain/persistence models
  — significant refactor, needs ADR before work begins. See
  `notes/domain-model-separation.md`.
- **Agentic AI integration** (Priority 1000): Out of scope until protocol
  foundation is stable

---

## Spec Compliance Snapshot

| Spec area | Status |
|-----------|--------|
| BT-01–BT-11 | ✅ Implemented (BT-08 CLI is MAY, low priority) |
| CM-01–CM-04 | ✅ Implemented (CM-03-006 rename pending REFACTOR-1) |
| CM-02-008 | ❌ Vendor initial participant in create_case not verified (SC-1.3) |
| CM-05-001 | ❌ VulnerabilityRecord and Publication types missing (SC-1.1, SC-1.2) |
| CM-06 | ❌ CaseActor broadcast not implemented (PRIORITY-200, blocked by OUTBOX-1) |
| CM-07 / AR-07 | ❌ Action rules endpoint not implemented (CA-2, PRIORITY-200) |
| Handler Protocol (HP-*) | ✅ All 38 handlers registered (incl. update_case) |
| Semantic extraction (SE-*) | ✅ 38 patterns + UNKNOWN |
| Dispatch routing (DR-*) | ✅ DirectActivityDispatcher |
| Inbox endpoint (IE-*) | ✅ 202 + BackgroundTasks |
| Idempotency (ID-01, ID-04) | ✅ Handler-level guards present |
| Idempotency (ID-02, ID-03, ID-05) | ❌ HTTP-layer deduplication not implemented |
| Outbox (OX-01, OX-02) | ✅ Outbox populated by handlers |
| Outbox (OX-03, OX-04) | ❌ Delivery not implemented (OUTBOX-1) |
| EP-01 | ❌ EmbargoPolicy model not implemented (EP-1.1, EP-1.2) |
| Demo CLI (DC-01–DC-05) | ✅ Complete |
| Production readiness | ❌ Deferred |
