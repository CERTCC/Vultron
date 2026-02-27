# Implementation History

This file archives completed phases from `IMPLEMENTATION_PLAN.md`.
New entries are appended; do not edit past entries.

---

## Phase 0 & 0A — Report Demo (COMPLETE 2026-02-13)

- All 6 report handlers implemented with full business logic
- Demo script (`receive_report_demo.py`) refactored into three workflow demonstrations
- Rehydration system, status tracking, outbox processing, and actor ID resolution all working
- 454 tests passing at completion

### Commits

- a2fc317: "Refactor receive_report_demo.py into three separate workflow demonstrations"
- 17457e7: "zero out implementation notes after lessons learned"

---

## Phase 0.5 — Test Infrastructure Fix (COMPLETE 2026-02-18)

All router tests (18/18) fixed after resolving separate data layer instances in fixtures.

---

## Phase BT-1 — Behavior Tree Integration POC (COMPLETE 2026-02-18)

**Goal**: Integrate `py_trees` BT execution into `validate_report` handler as POC.

- BT bridge layer (`vultron/behaviors/bridge.py`)
- DataLayer-aware helper nodes (`vultron/behaviors/helpers.py`)
- Report BT nodes (`vultron/behaviors/report/nodes.py`, 10 node classes)
- Report validation tree (`vultron/behaviors/report/validate_tree.py`)
- Default policy (`vultron/behaviors/report/policy.py`, `AlwaysAcceptPolicy`)
- `validate_report` handler refactored to use BT
- ADR-0008 documenting `py_trees` choice
- Performance: P99 < 1ms (well within 100ms target)
- 456 tests passing at completion

---

## Phase BT-2.0 — CM-04 / ID-04-004 Compliance Audit (COMPLETE 2026-02-20)

- Verified `engage_case` and `defer_case` update `ParticipantStatus.rm_state` (not `CaseStatus`)
- Added idempotency guards to both handlers

---

## Phase BT-2.1 — `engage_case` / `defer_case` BTs (COMPLETE 2026-02-20)

- `ENGAGE_CASE` and `DEFER_CASE` added to `MessageSemantics`
- `EngageCase` (Join) and `DeferCase` (Ignore) patterns added
- `PrioritizationPolicy` and `AlwaysPrioritizePolicy` added to policy module
- BT nodes: `CheckParticipantExists`, `TransitionParticipantRMtoAccepted`,
  `TransitionParticipantRMtoDeferred`, `EvaluateCasePriority` (SSVC stub)
- `vultron/behaviors/report/prioritize_tree.py` with
  `create_engage_case_tree` and `create_defer_case_tree`
- `engage_case` and `defer_case` handlers registered
- `specs/prototype-shortcuts.md` PROTO-05-001 documented

---

## Phase BT-3 — Case Management + `initialize_case` Demo (COMPLETE 2026-02-22)

- `create_case` BT handler (`vultron/behaviors/case/create_tree.py`)
- BT nodes: `CheckCaseAlreadyExists`, `ValidateCaseObject`, `PersistCase`,
  `CreateCaseActorNode`, `EmitCreateCaseActivity`, `UpdateActorOutbox`
- `add_report_to_case` handler (procedural)
- `close_case` handler (procedural)
- `create_case_participant` and `add_case_participant_to_case` handlers
- `initialize_case_demo.py` demo script + dockerized in `docker-compose.yml`

---

## Phase BT-4 — Actor Invitation + `invite_actor` Demo (COMPLETE 2026-02-23)

- `invite_actor_to_case`, `accept_invite_actor_to_case`,
  `reject_invite_actor_to_case`, `remove_case_participant_from_case` handlers
- `invite_actor_demo.py` (accept + reject paths) + dockerized
- Fixed `RmInviteToCase` pattern: removed `object_=AOtype.ACTOR` (real actors
  have type "Organization"/"Person", not "Actor")

---

## Phase BT-5 — Embargo Management + `establish_embargo` Demo (COMPLETE 2026-02-23)

- All 7 embargo handlers: `create_embargo_event`, `add_embargo_event_to_case`,
  `remove_embargo_event_from_case`, `announce_embargo_event_to_case`,
  `invite_to_embargo_on_case`, `accept_invite_to_embargo_on_case`,
  `reject_invite_to_embargo_on_case`
- `establish_embargo_demo.py` (propose-accept and propose-reject paths) + dockerized
- Fixed `EmAcceptEmbargo` + `EmRejectEmbargo` `as_object` type to
  `EmProposeEmbargoRef`

---

## Phase BT-6 — Status Updates + Notes Handlers (COMPLETE 2026-02-23)

- Notes handlers: `create_note`, `add_note_to_case`, `remove_note_from_case`
- Status handlers: `create_case_status`, `add_case_status_to_case`,
  `create_participant_status`, `add_participant_status_to_participant`
- `ack_report` handler verified against `acknowledge.md`
- `status_updates_demo.py` + dockerized

---

## Phase BT-7 — Suggest Actor + Ownership Transfer (COMPLETE 2026-02-24)

- Handlers: `suggest_actor_to_case`, `accept_suggest_actor_to_case`,
  `reject_suggest_actor_to_case`, `offer_case_ownership_transfer`,
  `accept_case_ownership_transfer`, `reject_case_ownership_transfer`
- `suggest_actor_demo.py` + dockerized
- `transfer_ownership_demo.py` + dockerized
- Bug fix: `AcceptActorRecommendation`/`RejectActorRecommendation` wrap the
  `RecommendActor` Offer as their `object` (consistent with other Accept/Reject pairs)
- Bug fix: `match_field` in `activity_patterns.py` handles string URI refs
  before `ActivityPattern` check
- 525 tests passing at completion; subsequently grown to 554 passing

---

## Phase BT-8 — Missing MessageSemantics (COMPLETE 2026-02-24)

- `UPDATE_CASE` (`as:Update(VulnerabilityCase)`) fully wired: `MessageSemantics` enum
  value, `UpdateCasePattern`, `update_case` handler, and tests (BT-8.6–BT-8.9)
- `REENGAGE_CASE` (`as:Undo(object=RmDeferCase)`) — **decided not to implement as a
  separate semantic type**. Re-engagement is achieved by emitting a second
  `RmEngageCase` (`as:Join`) activity from the `DEFERRED` state. The `reengage_case()`
  factory in `vocab_examples.py` is retained as a legacy documentation artifact only.
  See `notes/activitystreams-semantics.md` for the rationale.
- `CHOOSE_PREFERRED_EMBARGO` (`as:Question`) — **deferred**. The core
  propose/accept/reject flow covers the vast majority of embargo workflows. The
  placeholder class in `vultron/as_vocab/activities/embargo.py` is retained; no
  handler or pattern wired. Revisit if multiple simultaneous embargo proposals
  prove necessary in practice.

---

## Phase DEMO-3.1–3.9 — Acknowledge, Manage Case, Initialize Participant (COMPLETE 2026-02-24)

- `acknowledge_demo.py` — submit → ack_report workflow + dockerized
- `manage_case_demo.py` — full RM lifecycle including defer/reengage via second
  `RmEngageCase` + dockerized
- `initialize_participant_demo.py` — standalone participant creation workflow +
  dockerized
- Tests: `test/scripts/test_acknowledge_demo.py`,
  `test/scripts/test_manage_case_demo.py`,
  `test/scripts/test_initialize_participant_demo.py`

---

## Phase DEMO-3.10–3.15 — Manage Embargo + Manage Participants Demos (COMPLETE 2026-02-26)

- `manage_embargo_demo.py` — full propose → accept → activate → terminate cycle;
  also demonstrates propose → reject → re-propose path + dockerized
- `manage_participants_demo.py` — full invite → accept → create_participant →
  add_to_case → create_status → add_status → remove_participant cycle;
  also demonstrates reject path + dockerized
- Tests: `test/scripts/test_manage_embargo_demo.py`,
  `test/scripts/test_manage_participants_demo.py`
- **All Phase DEMO-3 tasks complete**: 568 tests passing at completion

---

## Phase DEMO-4 — Unified Demo CLI (COMPLETE 2026-02-27)

All 19 tasks completed. Key achievements:

- **DEMO-4.1–4.2**: Shared utilities (`demo_step`, `demo_check`, HTTP helpers,
  `DataLayerClient`, `demo_environment` context manager) extracted to
  `vultron/demo/utils.py`; all demo scripts updated to import from there
- **DEMO-4.3**: All 12 `*_demo.py` scripts moved from `vultron/scripts/` to
  `vultron/demo/`; test imports updated from `test/scripts/` to `test/demo/`
- **DEMO-4.4**: `demo_environment(client)` context manager added to
  `vultron/demo/utils.py`; guaranteed teardown (setup + `reset_datalayer` +
  `clear_all_actor_ios`) even on exception; all demo scripts updated
- **DEMO-4.5–4.6**: `vultron/demo/cli.py` — `click`-based CLI with
  sub-commands for all 12 demos plus `all`; `--debug` and `--log-file`
  options on `main` group; `vultron-demo` entry point in `pyproject.toml`
- **DEMO-4.7–4.8**: Unified `demo` Docker service in
  `docker/docker-compose.yml` with `condition: service_healthy` on `api-dev`;
  individual per-demo services removed
- **DEMO-4.9–4.11**: `test/demo/test_cli.py`; demo tests migrated to
  `test/demo/`; `conftest.py` sets `DEFAULT_WAIT_SECONDS=0.0` eliminating
  all `time.sleep` calls in tests; `_helpers.py` `make_testclient_call`
  factory; demo suite ~10× faster
- **DEMO-4.12–4.14**: `integration_tests/demo/` with integration test script
  and `README.md`; `make integration-test` Makefile target
- **DEMO-4.15–4.19**: `vultron/demo/README.md`; updated
  `docs/howto/activitypub/activities/*.md`; two demo tutorials in
  `docs/tutorials/`; docstrings and `docs/reference/code/demo/*.md`

---

## Resolved Design Decisions

| # | Question | Decision |
|---|----------|----------|
| Q1 | Async dispatcher priority | DEFERRED — FastAPI BackgroundTasks sufficient |
| Q2 | Test organization | pytest markers (`@pytest.mark.unit/integration`) |
| Q3 | URI validation scope | Syntax-only (no reachability checks) |
| Q4 | Handler implementation order | Implement in BT phases by workflow |
| Q5 | Authorization | OUT OF SCOPE for prototype |
| Q6 | Duplicate detection storage | In-memory cache (Option A) when implemented |
| Q7 | Structured logging format | JSON format preferred |
| Q8 | Health check ready conditions | Data layer connectivity only initially |
| Q9 | Coverage enforcement | Threshold-based (80% overall, 100% critical paths) |
| Q10 | Response generation timing | Defer decision until Phase 5 |
