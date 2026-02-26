# Vultron API v2 Implementation Plan

**Last Updated**: 2026-02-26 (gap analysis refresh #8)

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

## Gap Analysis (2026-02-26, refresh #8)

### ✅ Phase DEMO-3 fully complete

All 15 tasks (DEMO-3.1–3.15) are done. All demo scripts exist in
`vultron/scripts/`, tests exist in `test/scripts/`, and Docker services exist
in `docker/docker-compose.yml`. The previous gap noting missing
`manage_embargo_demo` and `manage_participants_demo` is resolved.

### ❌ DEMO-4: Unified demo CLI not started (PRIORITY 10)

Per `plan/PRIORITIES.md` PRIORITY 10 and `specs/demo-cli.md`:

- No `vultron/demo/utils.py` with shared `demo_step`/`demo_check` utilities
- Demo scripts still in `vultron/scripts/` (not `vultron/demo/`)
- No `vultron/demo/cli.py` click-based CLI entry point
- No `vultron-demo` entry point in `pyproject.toml`
- Per-demo Docker services remain; unified `demo` service not created
- No `integration_tests/` directory or README

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

### Phase DEMO-4 — Unified Demo CLI (PRIORITY 10)

**Priority**: HIGHEST per `plan/PRIORITIES.md`
**References**: `specs/demo-cli.md`, `plan/IDEATION.md`
**Note**: TECHDEBT-2 tasks (steps 1–2 below) MUST be completed first to
provide a clean foundation before CLI wiring.

#### Step 1 — Extract shared demo utilities (TECHDEBT-2, part A)

- [x] **DEMO-4.1**: Create `vultron/demo/utils.py` with `demo_step`,
  `demo_check` context managers and HTTP client helpers extracted from
  existing demo scripts (DC-02-001)
  - Done when: `from vultron.demo.utils import demo_step, demo_check`
    succeeds and all demo scripts import from there
- [x] **DEMO-4.2**: Update all demo scripts in `vultron/scripts/` to import
  `demo_step`, `demo_check`, and client helpers from `vultron.demo.utils`
  instead of defining them locally (DC-02-001)
  - Done when: no demo script defines its own `demo_step`/`demo_check`
    and all tests still pass

#### Step 2 — Relocate demo scripts (TECHDEBT-2, part B)

- [x] **DEMO-4.3**: Move all `*_demo.py` scripts from `vultron/scripts/` to
  `vultron/demo/` (DC-02-002)
  - Each demo MUST remain directly invokable via `if __name__ == "__main__"`
    (DC-01-005)
  - Update all import paths in test files (`test/scripts/`) and Docker
    configs
  - Done when: all demos importable as `vultron.demo.<script_name>` and
    full test suite passes

#### Step 3 — Demo isolation (teardown logic)

- [x] **DEMO-4.4**: Add setup/teardown logic to each demo so it leaves the
  DataLayer clean regardless of success or failure (DC-03-001, DC-03-003)
  - Teardown MUST run even when the demo raises an exception
  - Done when: running any two demos in sequence leaves no cross-demo state
  - See `DEMO-4 Isolation Complexity` notes in `IMPLEMENTATION_NOTES.md` for 
    risks and potential approaches

#### Step 4 — Build the unified CLI

- [x] **DEMO-4.5**: Create `vultron/demo/cli.py` as a `click`-based CLI with
  a sub-command for each demo and an `all` sub-command (DC-01-001 through
  DC-01-004)
  - Sub-command names MUST match short names of corresponding demo scripts
    (e.g., `receive-report`, `initialize-case`)
  - `all` sub-command MUST stop and report failure on first demo failure
  - `all` MUST print a human-readable pass/fail summary on completion
- [x] **DEMO-4.6**: Register `vultron-demo = "vultron.demo.cli:main"` as an
  entry point in `pyproject.toml` (DC-01-001)
  - Done when: `vultron-demo --help` lists all demo sub-commands after
    `uv pip install -e .`

#### Step 5 — Docker packaging

- [x] **DEMO-4.7**: Add unified `demo` service to `docker/docker-compose.yml`
  depending on `api-dev` with `condition: service_healthy` (DC-04-001)
  - Docker entry point MUST launch the CLI interactively by default
  - When `DEMO` env var is set, run named sub-command non-interactively and
    exit (DC-04-002)
- [ ] **DEMO-4.8**: Remove individual per-demo Docker services from
  `docker-compose.yml` after verifying the unified service runs all demos
  successfully (DC-04-003)

#### Step 6 — Unit tests

- [ ] **DEMO-4.9**: Create `test/demo/test_cli.py` with unit tests for the
  unified CLI (DC-05-001 through DC-05-004)
  - Test that each sub-command invokes the correct demo function
  - Test that `all` invokes every demo exactly once in order (using mocks)
  - Test that CLI exits with non-zero status when a demo raises an exception
  - Done when: `uv run pytest test/demo/test_cli.py` passes
- [ ] **DEMO-4.10**: Refactor demo tests to maintain parallelism to the new 
  structure — e.g., `test/demo/test_receive_report.py` tests `receive_report_demo`
- [ ] **DEMO-4.11**: See note in `plan/IMPLEMENTATION_NOTES.md` about demo 
  test slowness and potential refactor or segmentation to speed up development iterations.
  Recommended: refactoring demo tests to remove redundancy.

#### Step 7 — Integration test

- [ ] **DEMO-4.12**: Create 
  `integration_tests/demo/run_demo_integration_test.sh`
  (or equivalent Python script) that starts `api-dev`, runs `vultron-demo
  all` inside the `demo` container, and verifies all demos complete without
  errors (DC-06-001)
- [ ] **DEMO-4.13**: Create `integration_tests/README.md` documenting how to
  run integration tests, what success looks like, and a note that these are
  manual acceptance tests (not run by `pytest`) (DC-06-002)
- [ ] **DEMO-4.14**: Add `make integration-test` Makefile target (DC-06-003)

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
