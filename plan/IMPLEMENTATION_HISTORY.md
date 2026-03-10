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

## Phase BUGFIX-1 — Pytest Logging Noise (COMPLETE 2026-02-27)

- Root-logger side effect in `app.py` fixed (BUGFIX-1.1)
- Spurious `print()` calls replaced in four test files (BUGFIX-1.2)
- Test output clean under `uv run pytest`

---

## Phase REFACTOR-1 — CM-03-006 Status History Renames (COMPLETE 2026-02-27)

- `VulnerabilityCase.case_status` (list) → `case_statuses`; `case_status` added
  as read-only property (REFACTOR-1.1)
- `CaseParticipant.participant_status` (list) → `participant_statuses`;
  `participant_status` added as read-only property (REFACTOR-1.2)
- All references in handlers, behaviors, and tests updated (REFACTOR-1.3)

---

## Phase TECHDEBT-1, TECHDEBT-5, TECHDEBT-6 (COMPLETE 2026-02-27 / 2026-03-06)

- **TECHDEBT-1**: Handlers split into `vultron/api/v2/backend/handlers/` submodule
  package with 8 files; `__init__.py` ~100 LOC; full test suite passes.
- **TECHDEBT-5**: `vultron/scripts/vocab_examples.py` → `vultron/as_vocab/examples/`
  package; split into 8 submodules (`_base`, `actor`, `case`, `embargo`, `note`,
  `participant`, `report`, `status`); compatibility shim provided.
- **TECHDEBT-6**: Shim `vultron/scripts/vocab_examples.py` removed (commit 29005e4);
  all callers updated to import directly from `vultron.as_vocab.examples`.

---

## Phase SPEC-COMPLIANCE-1 — Object Model Gaps (COMPLETE 2026-03-06)

- **SC-1.1**: `VulnerabilityRecord` Pydantic model added
  (`vultron/as_vocab/objects/vulnerability_record.py`); unit tests added.
- **SC-1.2**: `CaseReference` Pydantic model added
  (`vultron/as_vocab/objects/case_reference.py`); unit tests added.
  (Previously named `Publication`; renamed per commit ad46802.)
- **SC-1.3**: `create_case` BT verified to record vendor as initial
  `CaseParticipant`; `SetCaseAttributedTo` and `CreateInitialVendorParticipant`
  BT nodes added to `vultron/behaviors/case/nodes.py`.

---

## Phase SPEC-COMPLIANCE-2 — Embargo Policy Model (COMPLETE 2026-03-06)

- **EP-1.1**: `EmbargoPolicy` Pydantic model added
  (`vultron/as_vocab/objects/embargo_policy.py`).
- **EP-1.2**: `VultronActorMixin` + `VultronPerson`, `VultronOrganization`,
  `VultronService` subclasses added (`vultron/as_vocab/objects/vultron_actor.py`);
  16 new tests; actor AS types preserved.

---

## Phase SPEC-COMPLIANCE-3 partial — SC-3.1 + SC-PRE-1 (COMPLETE 2026-03-06)

- **SC-3.1**: `accepted_embargo_ids: list[str]` field added to `CaseParticipant`
  (CM-10-001, CM-10-003); serialization round-trip tests pass.
- **SC-PRE-1**: `CaseEvent` plain Pydantic model added
  (`vultron/as_vocab/objects/case_event.py`); `VulnerabilityCase.events:
  list[CaseEvent]` field and `record_event()` append-only helper added;
  19 tests in `test/as_vocab/test_case_event.py`. Key invariant: `received_at`
  is always set via `now_utc()` — callers MUST NOT pass `received_at` from
  an incoming activity payload.

---

## Phase PRIORITY-30 partial — P30-1 through P30-3 (COMPLETE 2026-03-06)

- **P30-1**: `vultron/api/v2/routers/triggers.py` created; `validate-report`
  endpoint with `ValidateReportRequest` model (extra="ignore"); structured 404
  helpers; outbox-diff strategy to retrieve resulting activity; registered in
  `v2_router.py`; 9 tests in `test/api/v2/routers/test_triggers.py`. 702 tests
  passing at completion.
- **P30-2**: `invalidate-report` and `reject-report` endpoints added; procedural
  implementation emitting `RmInvalidateReport` (TentativeReject) and
  `RmCloseReport` (Reject) respectively; empty `note` on `reject-report` logs
  WARNING per TB-03-004; 17 new tests; 719 tests passing.
- **P30-3**: `engage-case` and `defer-case` endpoints added; procedural
  implementation emitting `RmEngageCase` (Join) and `RmDeferCase` (Ignore);
  `CaseTriggerRequest` model; `_resolve_case` and `_update_participant_rm_state`
  helpers; 17 new tests; 736 tests passing.

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

---

## Phase PRIORITY-50 — Hexagonal Architecture (archived 2026-03-10)

All tasks complete, but active regressions V-02-R, V-03-R, V-10-R, V-11-R
remain. New violations V-13 through V-23 introduced in P60-2. See
`plan/PRIORITIES.md` Priority 65 and `notes/architecture-review.md`.

- [x] **P50-0**: Extract domain service layer from `triggers.py`; split into three
  focused router modules (`trigger_report.py`, `trigger_case.py`,
  `trigger_embargo.py`) and a `trigger_services/` backend package.
- [x] **ARCH-1.1** (R-01): `MessageSemantics` moved to `vultron/core/models/events.py`.
- [x] **ARCH-1.2** (R-02): `InboundPayload` domain type introduced; AS2 type removed
  from `DispatchActivity.payload`. *(regression V-02-R active)*
- [x] **ARCH-1.3** (R-03 + R-04): `wire/as2/parser.py` and `wire/as2/extractor.py`
  created; parsing and extraction consolidated.
- [x] **ARCH-1.4** (R-05 + R-06): DataLayer injected via port; handler map moved to
  adapter layer. *(regression V-10-R active)*
- [x] **ARCH-CLEANUP-1**: Shims deleted; all callers updated.
- [x] **ARCH-CLEANUP-2**: AS2 structural enums moved to `vultron/wire/as2/enums.py`.
- [x] **ARCH-CLEANUP-3**: `isinstance` checks against AS2 types removed.
  *(regression V-11-R active: pattern unchanged via `raw_activity`)*
- [x] **ARCH-ADR-9**: `docs/adr/0009-hexagonal-architecture.md` written.

---

## Phase PRIORITY-60 — Package Relocation (archived 2026-03-10)

- [x] **P60-1**: `vultron/as_vocab/` → `vultron/wire/as2/vocab/`
- [x] **P60-2**: `vultron/behaviors/` → `vultron/core/behaviors/`
  *(introduced violations V-13 through V-21 — addressed in P65)*
- [x] **P60-3**: `vultron/adapters/` package stub created. ✅ 2026-03-10

---

## Phase SPEC-COMPLIANCE-3 — Embargo Acceptance Tracking (archived 2026-03-10)

- [x] **SC-PRE-2**: `actor_participant_index` added to `VulnerabilityCase`.
- [x] **SC-3.2**: Accepted embargo ID recorded in `CaseParticipant.accepted_embargo_ids`.
- [x] **SC-3.3**: Guard in `update_case` logs WARNING when participant has not accepted.

---

## Technical Debt (housekeeping, archived 2026-03-10)

- [x] **TECHDEBT-3**: Object IDs standardized to URI form; ADR-0010 created. ✅
- [x] **TECHDEBT-4**: SUPERSEDED — shims deleted in ARCH-CLEANUP-1; remaining
  `OfferStatusEnum`/`VultronObjectType` relocation deferred to P70.
- [x] **TECHDEBT-7/9**: `NonEmptyString`/`OptionalNonEmptyString` type aliases
  introduced; empty-string validators replaced. ✅ 2026-03-10
- [x] **TECHDEBT-8**: `pyrightconfig.json` committed; Makefile target added. ✅
- [x] **TECHDEBT-10**: Pre-case events backfilled in case event log. ✅
- [x] **TECHDEBT-11**: Test layout mirrored to match source after P60-1/P60-2. ✅
- [x] **TECHDEBT-12**: Deprecated `HTTP_422_UNPROCESSABLE_ENTITY` replaced. ✅

