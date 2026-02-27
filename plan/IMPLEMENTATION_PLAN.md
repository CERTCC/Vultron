# Vultron API v2 Implementation Plan

**Last Updated**: 2026-02-27 (gap analysis refresh #9)

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

## Gap Analysis (2026-02-27, refresh #9)

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

---

## Prioritized Task List

### Phase DEMO-3 — Remaining ActivityPub Workflow Demo Scripts

**Status**: ✅ COMPLETE — See `plan/IMPLEMENTATION_HISTORY.md`

---

### Phase DEMO-4 — Unified Demo CLI

**Status**: ✅ COMPLETE — See `plan/IMPLEMENTATION_HISTORY.md`

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

Priority: TECHDEBT-1 and TECHDEBT-5 are MEDIUM per `plan/PRIORITIES.md`
(PRIORITY 20). TECHDEBT-2 is subsumed into DEMO-4 above. TECHDEBT-3 and
TECHDEBT-4 remain LOW.

- [x] TECHDEBT-2: Subsumed into Phase DEMO-4 (DEMO-4.1–4.3).

- [ ] TECHDEBT-1: Split large handlers module into submodules — move related
  handlers into `vultron/api/v2/backend/handlers/*.py` and re-export in
  `vultron.api.v2.backend.handlers.__init__`.
  Done when: handlers module size reduces below 400 LOC and full test-suite passes.

- [ ] TECHDEBT-5: Move `vultron/scripts/vocab_examples.py` to
  `vultron/as_vocab/examples/` and provide a compatibility shim for existing
  import paths.
  Done when: new location is used and existing import paths remain functional.

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
