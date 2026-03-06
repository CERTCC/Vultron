# Vultron API v2 Implementation Plan

**Last Updated**: 2026-03-06 (gap analysis refresh #13)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Completed phase history is in `plan/IMPLEMENTATION_HISTORY.md`.

### Current Status Summary

**Test suite**: 592 passing, 5581 subtests, 0 xfailed (2026-03-06)

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

## Gap Analysis (2026-03-06, refresh #13)

### ✅ Phase BUGFIX-1 fully complete

Root-logger side effect in `app.py` fixed (BUGFIX-1.1); spurious `print()`
calls replaced in four test files (BUGFIX-1.2). Test output is clean under
`uv run pytest`. Residual `--- Logging error ---` noise seen only under
PyCharm's test runner (closed-stream interaction) — not a project-code issue;
documented as known environment limitation in `plan/BUGS.md`.

### ✅ Phase REFACTOR-1 fully complete (CM-03-006)

`VulnerabilityCase.case_status` → `case_statuses` and
`CaseParticipant.participant_status` → `participant_statuses` renames done.
All tests pass; read-only property accessors in place.

### ✅ Phase DEMO-3 fully complete

All 15 tasks (DEMO-3.1–3.15) are done. All demo scripts exist in
`vultron/demo/`, tests exist in `test/demo/`, and Docker services exist
in `docker/docker-compose.yml`.

### ✅ Phase DEMO-4 fully complete

All 19 tasks (DEMO-4.1–4.19) are done. See `plan/IMPLEMENTATION_HISTORY.md`
for the full record.

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

`VulnerabilityRecord` and `CaseReference` Pydantic model types specified in
CM-05-001 do not exist in the codebase. Note: the spec renamed `Publication`
to `CaseReference` (commit ad46802, 2026-03-06). `specs/case-management.md`
CM-05-002 through CM-05-007 cover their lifecycle constraints.

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

### ✅ Shim removal complete (TECHDEBT-6)

`vultron/scripts/vocab_examples.py` shim removed in commit 29005e4.
All callers updated to import directly from `vultron.as_vocab.examples`.

### ❌ Multi-actor demos not yet started (PRIORITY 300)

`plan/IDEAS.md` defines three multi-actor demo scenarios (finder+vendor,
finder+vendor+coordinator, ownership-transfer+multi-vendor). These require
PRIORITY 100 (actor independence) and PRIORITY 200 (CaseActor broadcast) to
be meaningful. Design work needed first.

### ❌ AR-01-003 — missing unique `operation_id` on FastAPI routes

No `operation_id` kwargs are set on any FastAPI route decorator; FastAPI
auto-generates them from function names which may not be stable or unique
across router boundaries.

### ❌ CM-10 embargo acceptance tracking not implemented

`specs/case-management.md` CM-10 requires:
- CM-10-001: `CaseParticipant` MUST track which embargoes the participant
  has accepted
- CM-10-002: Embargo acceptances MUST be timestamped by the CaseActor at
  receipt (implements CM-02-009)
- CM-10-003: `CaseParticipant` SHOULD include `accepted_embargo_ids:
  list[str]` field
- CM-10-004: Before sharing case updates, MUST verify participant accepted
  current active embargo

None of these requirements are implemented; `CaseParticipant` has no
`accepted_embargo_ids` field. See Phase SPEC-COMPLIANCE-3.

### ❌ CM-02-009 — general trusted-timestamp requirement not implemented

`specs/case-management.md` CM-02-009 (added 2026-03-05) generalizes
trusted-timestamp logic to ALL state-changing messages received by the
CaseActor, not just embargo acceptances. No trusted-timestamp logic exists
in any handler. Addressed together with CM-10 in SPEC-COMPLIANCE-3.

### ❌ CS-08-001 — Optional string fields allow empty strings

`specs/code-style.md` CS-08-001 (added 2026-03-05) requires Optional string
fields to reject empty strings. No Pydantic validators enforce this invariant
across the object models. Added as TECHDEBT-7.

### ⚠️ Triggerable-behaviors spec now formal (P30 tasks partially pre-date it)

`specs/triggerable-behaviors.md` TB-01 through TB-07 was created since the
last plan refresh. The P30 tasks exist but do not reference TB spec IDs and
omit explicit tasks for: request body schema (TB-03), response body with
`activity` key (TB-04), per-actor DataLayer DI (TB-06), and outbox
publication (TB-07). P30 tasks updated below.

### ⚠️ `specs/object-ids.md` now formally specifies TECHDEBT-3

`specs/object-ids.md` OID-01 through OID-04 was created since the last plan
refresh, formalizing the TECHDEBT-3 task. TECHDEBT-3 updated below to
reference OID spec IDs.

### ❌ Pyright static type checking not configured (IMPL-TS-07-002)

`specs/tech-stack.md` IMPL-TS-07-002 (added 2026-03-06) requires the project
to adopt pyright for static type checking, starting with a gradual approach:
run pyright to inventory existing type errors as technical debt, then enforce
it on new/modified code. No pyright configuration exists yet. Added as
TECHDEBT-8.

---

## Prioritized Task List

### Phase DEMO-3 — Remaining ActivityPub Workflow Demo Scripts

**Status**: ✅ COMPLETE — See `plan/IMPLEMENTATION_HISTORY.md`

---

### Phase DEMO-4 — Unified Demo CLI

**Status**: ✅ COMPLETE — See `plan/IMPLEMENTATION_HISTORY.md`

---

### Phase BUGFIX-1 — Pytest Logging Noise (Priority: HIGH — developer quality of life)

**Status**: ✅ COMPLETE (2026-02-27)

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

**Status**: ✅ COMPLETE (2026-02-27)

- [x] **REFACTOR-1.1**: Rename `VulnerabilityCase.case_status` (list) →
  `case_statuses`; add `case_status` as read-only property returning
  `current_status` (most recent by timestamp)
  - Update `vulnerability_case.py`, all references in `handlers.py`,
    `behaviors/`, and tests
- [x] **REFACTOR-1.2**: Rename `CaseParticipant.participant_status` (list) →
  `participant_statuses`; add `participant_status` as read-only property
  - Update `case_participant.py`, all references in `handlers.py` and tests
- [x] **REFACTOR-1.3**: Run full test suite; fix all breakage; confirm 0 regressions

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

- [x] TECHDEBT-6: Remove `vultron/scripts/vocab_examples.py` shim — update
  `vultron/api/v1/routers/participants.py` and `vultron/api/v2/routers/datalayer.py`
  to import directly from `vultron.as_vocab.examples`; then delete the shim file.
  Done when: shim removed; all existing tests pass; no references to the old
  `vultron.scripts.vocab_examples` import path remain.

- [ ] TECHDEBT-3: Standardize object IDs to URL-like form — draft ADR
  `docs/adr/ADR-XXXX-standardize-object-ids.md` and implement a compatibility
  shim in the DataLayer that accepts existing IDs.
  Done when: ADR created and tests validate URL-like ID acceptance.
  **Reference**: `specs/object-ids.md` OID-01 through OID-04.

- [ ] TECHDEBT-4: Reorganize top-level modules (activity_patterns, semantic_map,
  enums) into small packages to reduce circular imports and improve
  discoverability.
  Done when: modules moved with minimal interface changes and tests pass.

- [ ] TECHDEBT-7: Add Pydantic validators rejecting empty strings in Optional[str]
  fields across `vultron/as_vocab/objects/` models (CS-08-001). Add tests
  asserting that empty-string values are rejected and `None` is accepted.
  Done when: validators present on all Optional[str] fields and tests pass.

- [ ] TECHDEBT-8: Configure pyright for gradual static type checking
  (IMPL-TS-07-002). Run `pyright` on the full codebase to generate a
  baseline error inventory; commit a `pyrightconfig.json` with `basic`
  strictness and a baseline `# type: ignore` budget comment in
  `pyproject.toml` or CI config. All new/modified files MUST pass pyright
  at `basic` level from this point forward.
  Done when: pyright config committed, baseline error count documented in
  `plan/IMPLEMENTATION_NOTES.md`, and CI (or `Makefile`) has a target that
  runs pyright on changed files only (or full suite).

References: `notes/codebase-structure.md`, `plan/IMPLEMENTATION_NOTES.md`,
`plan/IDEAS.md`, and files in `specs/`.

---

### Phase SPEC-COMPLIANCE-1 — Object Model Gaps (Priority: MEDIUM)

**Reference**: `specs/case-management.md` CM-05-*, CM-02-008

- [x] **SC-1.1**: Add `VulnerabilityRecord` Pydantic model (CM-05-001)
  — persistent identifier record (e.g., CVE number) with `name`, `url`,
  `case_id` fields. Add to `vultron/as_vocab/objects/`. Add unit tests.
- [x] **SC-1.2**: Add `CaseReference` Pydantic model (CM-05-001, CM-05-005)
  — typed external reference with required `url` field and optional `name`
  and `tags` fields; `tags` aligned with CVE JSON schema reference tag
  vocabulary. Add to `vultron/as_vocab/objects/`. Add unit tests asserting
  `url` is required and `name`/`tags` are optional.
- [x] **SC-1.3**: Verify `create_case` BT records vendor as initial
  `CaseParticipant` before other participants (CM-02-008); add test asserting
  vendor `attributed_to` is set on case at creation.

---

### Phase SPEC-COMPLIANCE-2 — Embargo Policy Model (Priority: MEDIUM)

**Reference**: `specs/embargo-policy.md` EP-01

- [x] **EP-1.1**: Add `EmbargoPolicy` Pydantic model (EP-01-001 to EP-01-004)
  with `actor_id`, `inbox`, `preferred_duration_days`,
  `minimum_duration_days`, `maximum_duration_days`, `notes` fields.
  Add to `vultron/as_vocab/objects/embargo_policy.py`. Add unit tests.
- [x] **EP-1.2**: Add `embargo_policy` optional field to `VultronActor` (or
  equivalent actor profile model) referencing the `EmbargoPolicy` record.
  **Completed**: `VultronActorMixin` + `VultronPerson`, `VultronOrganization`,
  `VultronService` subclasses in `vultron/as_vocab/objects/vultron_actor.py`.
  Actor AS types preserved. 16 new tests; 665 pass.

---

### Phase SPEC-COMPLIANCE-3 — Embargo Acceptance Tracking + Trusted Timestamps
(Priority: MEDIUM)

**Reference**: `specs/case-management.md` CM-10, CM-02-009

- [ ] **SC-3.1**: Add `accepted_embargo_ids: list[str]` field to
  `CaseParticipant` (CM-10-001, CM-10-003). Update serialization tests;
  confirm round-trip through `object_to_record`/`record_to_object`
  preserves the field.
- [ ] **SC-3.2**: In `accept_invite_to_embargo_on_case` and
  `accept_invite_actor_to_case` handlers, record the accepted embargo ID
  in `CaseParticipant.accepted_embargo_ids` using the CaseActor's
  trusted timestamp at time of receipt rather than any participant-supplied
  timestamp (CM-10-002, CM-02-009). Add tests asserting that the ID is
  appended and the timestamp is server-generated.
- [ ] **SC-3.3**: Add a guard in `update_case` (or a shared helper) that
  checks each active participant has accepted the current embargo before
  the update is broadcast (CM-10-004). For prototype: log a WARNING when
  a participant has not accepted; full enforcement is PRIORITY-200
  (CaseActor broadcast). Add unit tests for the check logic.

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

**Reference**: `plan/PRIORITIES.md` PRIORITY 30,
`specs/triggerable-behaviors.md` TB-01 through TB-07,
`notes/triggerable-behaviors.md`, `docs/topics/behavior_logic/`

Design and implementation of API-level trigger endpoints for behaviors the
local actor initiates based on internal state (not purely reactive to messages).
Candidate behaviors from `docs/topics/behavior_logic/`:

- RM behaviors: validate-report, invalidate-report, reject-report,
  engage-case, defer-case, close-report (TB-02-001)
- EM behaviors: propose-embargo, evaluate-embargo, terminate-embargo
  (TB-02-002)

- [ ] **P30-1**: Implement the trigger router scaffolding and first endpoint:
  create `vultron/api/v2/routers/triggers.py`; register it in `v2_router.py`;
  add `POST /actors/{actor_id}/trigger/validate-report` that accepts a JSON
  body with `offer_id` (TB-01-001, TB-01-002, TB-01-004, TB-03-001),
  validates required fields (return 422 on missing `offer_id`; TB-03-001),
  ignores unknown fields (TB-03-002), invokes the `validate_report` BT via
  `vultron/behaviors/bridge.py` (TB-05-001, TB-05-002), adds the resulting
  activity to the actor's outbox (TB-07-001), and returns HTTP 202 with
  `{"activity": {...}}` body (TB-04-001). Inject DataLayer via
  `Depends(get_datalayer)` (TB-06-001, TB-06-002). Add unit + integration
  tests (TB-01, TB-03, TB-04, TB-05, TB-06, TB-07 verification).
- [ ] **P30-2**: Add `POST /actors/{actor_id}/trigger/invalidate-report` and
  `POST /actors/{actor_id}/trigger/reject-report` endpoints (TB-02-001).
  `reject-report` MUST require a non-empty `note` field (TB-03-004,
  CS-08-001). Add tests for both happy-path and missing-`note` error.
- [ ] **P30-3**: Add `POST /actors/{actor_id}/trigger/engage-case` and
  `POST /actors/{actor_id}/trigger/defer-case` endpoints (TB-02-001).
  Both require `case_id` in request body (TB-03-001). Add tests.
- [ ] **P30-4**: Add `POST /actors/{actor_id}/trigger/close-report` endpoint
  (TB-02-001) with `offer_id` in request body. Add tests.
- [ ] **P30-5**: Add EM trigger endpoints: `propose-embargo`,
  `evaluate-embargo`, `terminate-embargo` (TB-02-002). Each requires
  `case_id` in request body (TB-03-001). Add tests.
- [ ] **P30-6**: Add a `trigger` sub-command to the `vultron-demo` CLI
  exercising at least one trigger endpoint end-to-end; update
  `docs/reference/code/demo/*.md` to document the new command.

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

### Phase PRIORITY-300 — Multi-Actor Demos (PRIORITY 300)

**Blocked by**: PRIORITY-100 (actor independence), PRIORITY-200 (CaseActor
broadcast)
**Reference**: `plan/PRIORITIES.md` PRIORITY 300, `plan/IDEAS.md`

Three multi-actor demo scenarios are defined in `plan/IDEAS.md`. Each requires
actors to run in independent containers communicating via the Vultron Protocol.

- [ ] **D5-1**: Confirm that PRIORITY-100 and PRIORITY-200 are complete before
  starting this phase; update design if needed.
- [ ] **D5-2**: Implement Demo Scenario 1 (finder + vendor): finder reports
  vulnerability, vendor accepts, case created with embargo, two vulnerabilities
  added. Dockerized with two actor containers + CaseActor container.
- [ ] **D5-3**: Implement Demo Scenario 2 (finder + vendor + coordinator):
  full three-actor workflow including coordinator embargo policy, invite/accept,
  CVE record creation, PXA state transitions, case closure.
- [ ] **D5-4**: Implement Demo Scenario 3 (ownership transfer + multi-vendor):
  ownership transfer, coordinator invites additional vendors, embargo extension
  negotiation, multi-vendor simultaneous disclosure, case closure.
- [ ] **D5-5**: Add integration tests and Docker Compose configs for each scenario.

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
| CM-01–CM-04 | ✅ Implemented (CM-03-006 rename complete in REFACTOR-1) |
| CM-02-007 | ✅ `VulnerabilityCase.notes` field present; `add_note_to_case` appends correctly |
| CM-02-008 | ❌ Vendor initial participant in create_case not verified (SC-1.3) |
| CM-02-009 | ❌ General trusted-timestamp requirement not implemented (SC-3.2) |
| CM-05-001 | ❌ VulnerabilityRecord and CaseReference types missing (SC-1.1, SC-1.2) |
| CM-06 | ❌ CaseActor broadcast not implemented (PRIORITY-200, blocked by OUTBOX-1) |
| CM-07 / AR-07 | ❌ Action rules endpoint not implemented (CA-2, PRIORITY-200) |
| CM-10 | ❌ Embargo acceptance tracking not implemented (SC-3.1, SC-3.2, SC-3.3) |
| Handler Protocol (HP-*) | ✅ All 38 handlers registered (incl. update_case) |
| Semantic extraction (SE-*) | ✅ 38 patterns + UNKNOWN |
| Dispatch routing (DR-*) | ✅ DirectActivityDispatcher |
| Inbox endpoint (IE-*) | ✅ 202 + BackgroundTasks |
| Idempotency (ID-01, ID-04) | ✅ Handler-level guards present |
| Idempotency (ID-02, ID-03, ID-05) | ❌ HTTP-layer deduplication not implemented |
| Outbox (OX-01, OX-02) | ✅ Outbox populated by handlers |
| Outbox (OX-03, OX-04) | ❌ Delivery not implemented (OUTBOX-1) |
| EP-01 | ✅ EmbargoPolicy model (EP-1.1) and VultronActor mixin (EP-1.2) implemented |
| TB-01–TB-07 | ❌ Triggerable behavior endpoints not implemented (P30-1 through P30-6) |
| OID-01–OID-04 | ❌ Object ID standardization not started (TECHDEBT-3) |
| CS-08-001 | ❌ Optional empty-string validation not implemented (TECHDEBT-7) |
| IMPL-TS-07-002 | ❌ Pyright not configured (TECHDEBT-8) |
| Demo CLI (DC-01–DC-05) | ✅ Complete |
| BUGFIX-1 (logging/print) | ✅ Complete |
| REFACTOR-1 (CM-03-006) | ✅ Complete |
| Production readiness | ❌ Deferred |
