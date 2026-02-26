# Vultron API v2 Implementation Plan

**Last Updated**: 2026-02-24 (gap analysis refresh #7)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Completed phase history is in `plan/IMPLEMENTATION_HISTORY.md`.

### Current Status Summary

**Test suite**: 557 passing, 5581 subtests, 0 xfailed (2026-02-24)

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
`initialize_participant_demo.py`

---

## Gap Analysis (2026-02-24, refresh #7)

### ❌ Demo scripts missing for PRIORITIES.md higher-priority workflows

| Howto doc | Existing demo | Gap |
|---|---|---|
| `manage_embargo.md` | partial (`establish_embargo_demo`) | Full propose/accept/reject/terminate cycle not demoed |
| `manage_participants.md` | partial (`invite_actor_demo`) | Status + remove paths not demoed |

### ❌ CM-03-006 field rename not implemented

`VulnerabilityCase.case_status` is a `list[CaseStatusRef]` (history) but
named in the singular; spec requires `case_statuses`. Same for
`CaseParticipant.participant_status`.

### ❌ Outbox delivery not implemented (lower priority)

`actor_io.py` stub logs placeholder messages instead of writing to recipient
actor inboxes (OX-03-001, OX-04-001, OX-04-002).

---

## Prioritized Task List

### Phase DEMO-3 — Remaining ActivityPub Workflow Demo Scripts

**Priority**: HIGH per `plan/PRIORITIES.md`
**References**: `docs/howto/activitypub/activities/`
**Pattern**: Follow existing demo scripts; use `demo_step` / `demo_check` context managers

#### acknowledge_demo.py

- [x] **DEMO-3.1**: Create `vultron/scripts/acknowledge_demo.py`
  - Workflow from `acknowledge.md`: submit report → ack_report (RmReadReport)
    → optionally validate or invalidate
  - Show RM state transitions at each step
- [x] **DEMO-3.2**: Add `test/scripts/test_acknowledge_demo.py`
- [x] **DEMO-3.3**: Add `acknowledge-demo` service to `docker/docker-compose.yml`
  and corresponding Dockerfile target

#### manage_case_demo.py

- [x] **DEMO-3.4**: Create `vultron/scripts/manage_case_demo.py`
  - Full lifecycle from `manage_case.md`: submit → validate → create_case →
    engage/defer → reengage (via second `RmEngageCase`) → close
  - Demonstrate both engage and defer/reengage paths
- [x] **DEMO-3.5**: Add `test/scripts/test_manage_case_demo.py`
- [x] **DEMO-3.6**: Add `manage-case-demo` service to docker-compose.yml

#### initialize_participant_demo.py

- [x] **DEMO-3.7**: Create `vultron/scripts/initialize_participant_demo.py`
  - Workflow from `initialize_participant.md`: create_case_participant →
    add_case_participant_to_case (standalone, not requiring prior invite)
  - Show case participant list before and after
- [x] **DEMO-3.8**: Add `test/scripts/test_initialize_participant_demo.py`
- [x] **DEMO-3.9**: Add `initialize-participant-demo` service to docker-compose.yml

#### manage_embargo_demo.py

- [x] **DEMO-3.10**: Create `vultron/scripts/manage_embargo_demo.py`
  - Full cycle from `manage_embargo.md`: propose → accept → activate → terminate
  - Also demonstrate propose → reject → re-propose path
- [x] **DEMO-3.11**: Add `test/scripts/test_manage_embargo_demo.py`
- [x] **DEMO-3.12**: Add `manage-embargo-demo` service to docker-compose.yml

#### manage_participants_demo.py

- [x] **DEMO-3.13**: Create `vultron/scripts/manage_participants_demo.py`
  - Full cycle from `manage_participants.md`: invite → accept →
    create_participant → add_to_case → create_status → add_status →
    remove_participant
  - Demonstrate reject path as well
- [x] **DEMO-3.14**: Add `test/scripts/test_manage_participants_demo.py`
- [x] **DEMO-3.15**: Add `manage-participants-demo` service to docker-compose.yml

---

### Phase REFACTOR-1 — CM-03-006: Status History Field Renames (Priority 50)

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

## Technical debt (housekeeping)

Priority: LOW–MEDIUM. These tasks reduce long-term maintenance and should be
addressed as time permits.

- [ ] TECHDEBT-1: Split large handlers module into submodules — move related
  handlers into `vultron/api/v2/backend/handlers/*.py` and re-export in
  `vultron.api.v2.backend.handlers.__init__`.
  Done when: handlers module size reduces below 400 LOC and full test-suite passes.

- [ ] TECHDEBT-2: Extract demo utilities and centralize demos — move
  `demo_step`/`demo_check` context managers and shared client helpers to
  `vultron/demo/utils.py` and relocate demo scripts to `vultron/demo/`.
  Done when: demos import from `vultron.demo.utils` and demo tests pass.

- [ ] TECHDEBT-3: Standardize object IDs to URL-like form — draft ADR
  `docs/adr/ADR-XXXX-standardize-object-ids.md` and implement a compatibility
  shim in the DataLayer that accepts existing IDs.
  Done when: ADR created and tests validate URL-like ID acceptance.

- [ ] TECHDEBT-4: Reorganize top-level modules (activity_patterns, semantic_map,
  enums) into small packages to reduce circular imports and improve
  discoverability.
  Done when: modules moved with minimal interface changes and tests pass.

- [ ] TECHDEBT-5: Move `vultron/scripts/vocab_examples.py` to
  `vultron/as_vocab/examples/` and provide a compatibility shim for existing
  import paths.
  Done when: new location is used and existing import paths remain functional.

References: `notes/codebase-structure.md`, `plan/IMPLEMENTATION_NOTES.md`,
`plan/IDEATION.md`, and files in `specs/`.

---

## Deferred (Per PRIORITIES.md)

The following are deferred until BT phases and demos are complete:

- **Production readiness** (Phase 1–3): Request validation, error responses,
  health check readiness probe, structured logging, idempotency/duplicate detection,
  test coverage enforcement — all `PROD_ONLY` or low-priority
- **Response generation** (Phase 5): Accept/Reject/TentativeReject response builders,
  outbox delivery with retry/backoff — see historical task list in
  `IMPLEMENTATION_HISTORY.md`
- **Code quality** (Phase 6): `mypy`, `black` audit, docstring coverage
- **Performance / scalability** (Phase 7): Queue-based dispatcher, DB replacement,
  rate limiting

---

## Spec Compliance Snapshot

| Spec area | Status |
|-----------|--------|
| BT-01–BT-11 | ✅ Implemented (BT-08 CLI is MAY, low priority) |
| CM-01–CM-04 | ✅ Implemented (CM-03-006 rename pending REFACTOR-1) |
| Handler Protocol (HP-*) | ✅ All 38 handlers registered (incl. update_case) |
| Semantic extraction (SE-*) | ✅ 38 patterns + UNKNOWN |
| Dispatch routing (DR-*) | ✅ DirectActivityDispatcher |
| Inbox endpoint (IE-*) | ✅ 202 + BackgroundTasks |
| Idempotency (ID-01, ID-04) | ✅ Handler-level guards present |
| Idempotency (ID-02, ID-03, ID-05) | ❌ HTTP-layer deduplication not implemented |
| Outbox (OX-01, OX-02) | ✅ Outbox populated by handlers |
| Outbox (OX-03, OX-04) | ❌ Delivery not implemented |
| Production readiness | ❌ Deferred |
