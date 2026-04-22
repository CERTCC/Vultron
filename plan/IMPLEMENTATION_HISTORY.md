# Implementation History

This file archives completed phases from `IMPLEMENTATION_PLAN.md`.
**New entries MUST be added at the END of this file.** Do not insert entries
at the top or in the middle; this is an append-only log. Past entries MUST
NOT be edited. Include date completed when known.

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

## BUG-2026032601 — Pytest Collection Warning Cleanup (COMPLETE 2026-03-26)

- Issue: `uv run pytest` emitted a `PytestCollectionWarning` because
  `test/bt/test_behaviortree/test_common.py` defined a helper enum named
  `TestEnum`, which matched pytest's test-class naming pattern.
- Root cause: pytest attempted to collect the enum as a test class, then
  warned because `enum.IntEnum` provides a constructor incompatible with test
  collection.
- Resolution: renamed the helper enum to `MockEnum` and added
  `test/test_pytest_collection_hygiene.py`, an AST-based regression test that
  fails if helper enums under `test/` use `Test*` names.
- Validation: `uv run pytest --tb=short 2>&1 | tail -5` → `1026 passed, 5581
  subtests passed in 26.27s`

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

---

## Lint cleanup — mypy and pyright baseline burn-down (COMPLETE 2026-03-26)

- Reduced `mypy` from 440 errors in 69 files to 0 without broad ignore
  rules; fixes focused first on shared protocols, DataLayer typing,
  AS2/domain model boundaries, and extractor/rehydration surfaces.
- Reduced `pyright` from 838 initial errors to 0 after the repository became
  more analyzable; the cleanup included preserving subclass identity in
  ActivityStreams registry decorators, tightening BT base typing, and
  updating stale `id=` / `object=` constructor call sites to
  `as_id=` / `as_object=`.
- Cleaned test infrastructure and fixtures so static analysis matches real
  runtime objects, especially around inbox/outbox handlers, persisted object
  round-trips, and BT mock state.
- Final validation completed with:
  - `uv run black vultron/ test/`
  - `uv run flake8 vultron/ test/`
  - `uv run mypy`
  - `uv run pyright`
  - `uv run pytest --tb=short 2>&1 | tail -5`
- Final result: `1025 passed, 1 warning, 5581 subtests passed in 35.29s`
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

## 2026-04-01 — D5-3 complete: three-actor demo scenario

- Added `vultron/demo/three_actor_demo.py`, a deterministic Finder + Vendor +
  Coordinator scenario that uses the dedicated `case-actor` container as the
  authoritative case host.
- Wired a new `vultron-demo three-actor` CLI sub-command in
  `vultron/demo/cli.py`.
- Extended `docker/docker-compose-multi-actor.yml` with a `coordinator`
  service, `VULTRON_COORDINATOR_BASE_URL`, a `DEMO=${DEMO:-two-actor}`
  selector for the `demo-runner`, and a new `coordinator-data` volume.
- Added `docker/seed-configs/seed-coordinator.json` and updated the existing
  multi-actor seed configs so Finder, Vendor, Coordinator, and CaseActor all
  pre-register the full peer mesh.
- Updated `docker/README.md` with the D5-3 command path:
  `DEMO=three-actor docker compose -f docker-compose-multi-actor.yml up --abort-on-container-exit demo-runner`.
- Added unit coverage in `test/demo/test_three_actor_demo.py` for seeding,
  authoritative case creation on CaseActor, full workflow execution, and CLI
  wiring.
- The demo workflow intentionally reuses existing protocol surfaces instead of
  adding new trigger APIs: Finder submits to Coordinator, Coordinator creates
  the case on CaseActor via `CreateCaseActivity`, links the report with
  `AddReportToCaseActivity`, invites participants via `RmInviteToCaseActivity`,
  and establishes the embargo with the existing embargo trigger/accept flow.
- Validation:
  - `uv run pytest test/demo/test_three_actor_demo.py -q`
  - `uv run black vultron/ test/ && uv run flake8 vultron/ test/ && uv run mypy && uv run pyright`
  - `./mdlint.sh`
  - `uv run pytest --tb=short 2>&1 | tail -5` (exit code 0; runtime buffered
    the final tail output, but the canonical command completed successfully)

---

## 2026-03-10 — SC-PRE-2 complete: actor_participant_index

### Design

`actor_participant_index: dict[str, str]` maps actor IDs (from
`CaseParticipant.attributed_to`) to participant IDs. Added to
`VulnerabilityCase` alongside two new methods:

- `add_participant(participant: CaseParticipant)` — appends the full object
  to `case_participants` and updates the index atomically. Requires a full
  `CaseParticipant` object (not a string ref) to derive the actor key.
- `remove_participant(participant_id: str)` — filters `case_participants`
  and removes the corresponding index entry.

### Handlers updated

- `add_case_participant_to_case` → calls `case.add_participant(participant)`
- `remove_case_participant_from_case` → calls `case.remove_participant(participant_id)`
- `accept_invite_actor_to_case` → calls `case.add_participant(participant)`;
  idempotency check now uses `actor_participant_index` (old check was
  comparing actor IDs against participant IDs and never matched).

### Notes for SC-3.2 / SC-3.3

The `actor_participant_index` is the prerequisite for SC-3.2 and SC-3.3.
SC-3.2 records the accepted embargo ID in `CaseParticipant.accepted_embargo_ids`
using the CaseActor's trusted timestamp. The index makes it efficient to
look up a participant from the actor ID when processing `Accept(Invite(...))` or
`Accept(Offer(Embargo))` activities.

SC-3.3 adds `_check_participant_embargo_acceptance()` as a module-level helper
in `vultron/api/v2/backend/handlers/case.py`. It is called from `update_case`
after the ownership check passes. The helper iterates `actor_participant_index`,
rehydrates each participant, and logs a WARNING if the participant's
`accepted_embargo_ids` does not include the case's `active_embargo` ID.
Full enforcement (withholding the broadcast) is deferred to PRIORITY-200 when
the outbox delivery pipeline is implemented.

---

## 2026-03-10 — Gap analysis refresh #22: new gaps identified

### P70 DataLayer refactor — when to plan

`notes/domain-model-separation.md` says the DataLayer relocation SHOULD be planned
together with PRIORITY-100 (actor independence). The P70 tasks in the plan follow
that guidance: P70-1 relocates the port Protocol and TinyDB adapter to their
correct architectural homes, which unblocks the per-actor isolation work in
PRIORITY-100. P60-3 must come first (adapters package stub needed before TinyDB
moves there).

### TECHDEBT-4 superseded

TECHDEBT-4 ("reorganize top-level modules `activity_patterns`, `semantic_map`,
`enums`") is largely complete:

- `vultron/activity_patterns.py` and `vultron/semantic_map.py` deleted in
  ARCH-CLEANUP-1.
- AS2 structural enums moved from `vultron/enums.py` to `vultron/wire/as2/enums.py`
  in ARCH-CLEANUP-2.
- `vultron/enums.py` now only re-exports `MessageSemantics` plus defines
  `OfferStatusEnum` and `VultronObjectType`.

Remaining work: move `OfferStatusEnum` and `VultronObjectType` to their proper
homes and delete `vultron/enums.py`. Tracked in TECHDEBT-4 (marked superseded in
plan) and P70-2.

---

## 2026-03-09 — Hexagonal architecture refactor elevated to PRIORITY 50 (immediate next)

Per updated `plan/PRIORITIES.md`, the hexagonal architecture refactor with `triggers.py`
as the starting point is now the top priority. The plan has been updated accordingly:
`Phase ARCH-1` is renamed to `Phase PRIORITY-50` and moved to be the immediate next
phase after PRIORITY-30 (now complete). The old "PRIORITY 150" label in the plan was
incorrect; PRIORITIES.md has always listed this as Priority 50.

---

## 2026-03-09 — P30-4 `close-report` vs `reject-report` distinction

Both `reject-report` and `close-report` emit `RmCloseReport` (`as_Reject`), but
they differ in context:

- `reject-report` hard-rejects an incoming report offer (offer not yet validated;
  `object=offer.as_id`)
- `close-report` closes a report after the RM lifecycle has proceeded (RM → C
  transition; emits RC message)

The existing `trigger_reject_report` implementation uses `offer_id` as its target.
The `trigger_close_report` implementation should also use `offer_id` but should
validate that the offer's report is in an appropriate RM state for closure (not
just any offered report). This distinction should be documented in the endpoint
docstring.

## 2026-03-09 — CS-09-002 duplication in triggers.py request models

`ValidateReportRequest` and `InvalidateReportRequest` in `triggers.py` are
structurally identical (both have `offer_id: str` and `note: str | None`). Per
CS-09-002, these should be consolidated into a single base model with the other
as a subclass or alias. Low-priority but worth addressing when the file is next
modified.

---

## 2026-03-09 — P30-4 complete: close-report trigger endpoint

`POST /actors/{actor_id}/trigger/close-report` added. Emits `RmCloseReport`
(RM → C transition), updates offer/report status and actor outbox, returns
HTTP 409 if already CLOSED. 9 unit tests added.

Also converted `RM` from plain `Enum` to `StrEnum` for consistency with `EM`.
This changes `str(RM.X)` from `"RM.REPORT_MANAGEMENT_X"` to `"X"`, resulting
in cleaner BT node names (e.g., `q_rm_in_CLOSED` instead of
`q_rm_in_RM.REPORT_MANAGEMENT_CLOSED`). Updated `test_conditions.py` to check
`state.value` in node name instead of `state.name`.

---

`specs/architecture.md` and `notes/architecture-review.md` were added since the
last plan refresh. The review identifies 11 violations (V-01 to V-11) and a
remediation plan (R-01 to R-06). The most impactful violations are:

- **V-01**: `MessageSemantics` mixed with AS2 structural enums in `vultron/enums.py`
- **V-02**: `DispatchActivity.payload: as_Activity` (AS2 type leaks into core)
- **V-04**: `verify_semantics` decorator re-invokes `find_matching_semantics`
  (second AS2-to-domain mapping point, violates Rule 4)

Phase ARCH-1 now tracks this work. ARCH-1.1 (R-01) must be done before ARCH-1.2
(R-02), which must precede ARCH-1.3 (R-03/R-04).

### Approach for P50-0: Extract service layer from `triggers.py` — **COMPLETE**

`triggers.py` is 1274 lines with all nine trigger endpoint functions each containing
inline domain logic (data lookups, state transitions, activity construction, outbox
updates). The fix is a two-step operation within one agent cycle:

**Step 1 — Create `vultron/api/v2/backend/trigger_services/` package** ✓:

- `report.py` — service functions for `validate_report`, `invalidate_report`,
  `reject_report`, `close_report`
- `case.py` — service functions for `engage_case`, `defer_case`
- `embargo.py` — service functions for `propose_embargo`, `evaluate_embargo`,
  `terminate_embargo`

Each service function signature:

```python
def svc_validate_report(actor_id: str, offer_id: str, note: str | None, dl: DataLayer) -> dict:
    ...
```

The `DataLayer` is passed in from the router (via `Depends(get_datalayer)`), not
fetched inside the service.

**Step 2 — Thin-ify and split the router** ✓:

- Split `triggers.py` into `trigger_report.py`, `trigger_case.py`,
  `trigger_embargo.py` in `vultron/api/v2/routers/`
- Each router function: validate request → call service → return response
- `triggers.py` deleted ✓

**Additional cleanup** ✓:

- Consolidated `ValidateReportRequest`, `InvalidateReportRequest`, and
  `CloseReportRequest` (structurally identical — CS-09-002) into shared base
  `ReportTriggerRequest` in `_models.py`
- Trigger tests split into `test_trigger_report.py`, `test_trigger_case.py`,
  `test_trigger_embargo.py`; service-layer unit tests added in
  `test/api/v2/backend/test_trigger_services.py`
- Test count: 777 → 815 passing

### Why start with `triggers.py` before ARCH-1.1?

ARCH-1.1 through ARCH-1.4 are deep structural changes affecting many files across
the codebase. P50-0 (triggers.py service extraction) is scoped to a single large
file, delivers immediate architectural value (no domain logic in routers), and does
not require the broader `core/`/`wire/`/`adapters/` directory restructure to be
in place first. It also establishes the pattern that ARCH-1.1 through 1.4 will
generalize to the rest of the codebase.

ARCH-1.1 and ARCH-1.2 remain prerequisites for ARCH-1.3 and ARCH-1.4 as documented
in `notes/architecture-review.md`.

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

## 2026-03-10 — P60-1 complete: vultron/as_vocab moved to vultron/wire/as2/vocab

> ✅ Captured in `docs/adr/0009-hexagonal-architecture.md` (P60-1 marked
> complete) and `notes/codebase-structure.md` and
> `notes/architecture-ports-and-adapters.md` (file layout updated 2026-03-10).

### What changed

- Copied entire `vultron/as_vocab/` tree to `vultron/wire/as2/vocab/` (keeping
  all sub-packages: `base/`, `objects/`, `activities/`, `examples/`, plus
  `errors.py`, `type_helpers.py`).
- Updated all internal imports within the moved files from `vultron.as_vocab.*`
  to `vultron.wire.as2.vocab.*`.
- Updated ~90 external callers across `vultron/api/`, `vultron/behaviors/`,
  `vultron/demo/`, `vultron/wire/as2/`, and `test/`.
- Deleted `vultron/as_vocab/` entirely (no shim left behind).
- 822 tests pass.

---

## 2026-03-10 — ARCH-CLEANUP-3 complete: isinstance AS2 checks replaced (V-11, V-12)

> ✅ Captured in `notes/architecture-review.md` (V-11, V-12 marked remediated
> by ARCH-CLEANUP-3) and `docs/adr/0009-hexagonal-architecture.md` (2026-03-10).

### What changed

- **`handlers/report.py`**: `create_report` and `submit_report` now check
  `dispatchable.payload.object_type != "VulnerabilityReport"` instead of
  `isinstance`. `validate_report` uses `getattr(accepted_report, "as_type", None)`.
  Local `VulnerabilityReport` imports removed from all three handlers.
- **`handlers/case.py`**: `update_case` uses `getattr(incoming, "as_type", None) ==
  "VulnerabilityCase"`. Local `VulnerabilityCase` import removed.
- **`trigger_services/report.py`**: `_resolve_offer_and_report` uses `getattr`
  as_type check. `VulnerabilityReport` module-level import removed.
- **`trigger_services/_helpers.py`**: `resolve_case` and
  `update_participant_rm_state` use `getattr` as_type checks. `VulnerabilityCase`
  import retained for the `-> VulnerabilityCase` return type annotation.
- **`test/test_behavior_dispatcher.py`**: Removed `as_TransitiveActivityType` and
  `VulnerabilityReport` imports. `as_type` assertion uses string `"Create"`.
  Dispatch test uses `MagicMock` for `raw_activity` instead of full AS2 construction.
- **`test/api/test_reporting_workflow.py`**: `_call_handler` now populates
  `InboundPayload.object_type` from `activity.as_object.as_type` (mirrors
  `prepare_for_dispatch`), so handler type guards work correctly in tests.

822 tests pass.

### Shim modules deleted

- Deleted `vultron/activity_patterns.py`, `vultron/semantic_map.py`, and
  `vultron/semantic_handler_map.py` (all were pure re-export shims).
- Updated all callers to import from canonical locations:
  - `test/test_semantic_activity_patterns.py`: `ActivityPattern` and
    `SEMANTICS_ACTIVITY_PATTERNS` now imported from `vultron.wire.as2.extractor`.
  - `test/api/test_reporting_workflow.py`: `find_matching_semantics` now imported
    from `vultron.wire.as2.extractor`.
  - `test/test_semantic_handler_map.py`: Shim-specific tests removed; test now
    uses `SEMANTICS_HANDLERS` from `vultron.api.v2.backend.handler_map` directly.
- 822 tests pass.

---

### Handler registry added

- **`vultron/api/v2/backend/handler_map.py`** (new): Module-level handler registry in
  the adapter layer. `SEMANTICS_HANDLERS` dict maps `MessageSemantics` → handler
  functions with plain module-level imports (no lazy imports needed since this file
  is already in the adapter layer). This addresses V-09.

- **`vultron/semantic_handler_map.py`**: Converted to a backward-compat shim that
  re-exports `SEMANTICS_HANDLERS` and a `get_semantics_handlers()` wrapper from
  the new location. Can be deleted once all callers are updated.

- **`vultron/behavior_dispatcher.py`**: `DispatcherBase` now accepts `dl: DataLayer`
  and `handler_map: dict[MessageSemantics, BehaviorHandler]` in its constructor.
  `_handle()` passes `dl=self.dl` to each handler. `_get_handler_for_semantics()`
  uses `self._handler_map` directly (no lazy import). `get_dispatcher()` updated to
  accept `dl` and `handler_map` parameters.

- **`vultron/api/v2/backend/inbox_handler.py`**: Module-level `DISPATCHER` now
  constructed with `get_datalayer()` + `SEMANTICS_HANDLERS` injected. The lazy
  import in `_get_handler_for_semantics` is gone; the coupling to the handler map
  now lives in the adapter layer only.

- **All handler files** (`report.py`, `case.py`, `embargo.py`, `actor.py`, `note.py`,
  `participant.py`, `status.py`, `unknown.py`): Each handler function signature
  updated to `(dispatchable: DispatchActivity, dl: DataLayer) -> None`. All
  `from vultron.api.v2.datalayer.tinydb_backend import get_datalayer` lazy imports
  and `dl = get_datalayer()` calls removed. `DataLayer` imported at module level from
  `vultron.api.v2.datalayer.abc`. This addresses V-10.

- **`vultron/types.py`**: `BehaviorHandler` Protocol updated to
  `__call__(self, dispatchable: DispatchActivity, dl: DataLayer) -> None`.

- **`vultron/api/v2/backend/handlers/_base.py`**: `verify_semantics` wrapper updated
  to accept and forward `dl: DataLayer`.

- **Tests**: All `@patch("vultron.api.v2.datalayer.tinydb_backend.get_datalayer")`
  patches in `test_handlers.py` replaced with direct `mock_dl` argument passing.
  `test_behavior_dispatcher.py` updated to construct dispatcher with injected DL
  and handler map. 824 tests pass (up from 822).

### Phase PRIORITY-50 is now complete (ARCH-1.1 through ARCH-1.4)

All four ARCH-1.x tasks are done. The hexagonal architecture violations V-01 through
V-10 have been remediated. The remaining violations in the inventory (V-11, V-12)
are lower severity and can be addressed as part of subsequent work.

## 2026-03-09 — P30-6 complete: trigger sub-command in vultron-demo CLI

Added `vultron-demo trigger` sub-command backed by `vultron/demo/trigger_demo.py`.

Two end-to-end demo workflows are implemented:

- **Demo 1 (validate and engage)**: finder submits report via inbox → vendor
  calls `POST .../trigger/validate-report` → vendor calls
  `POST .../trigger/engage-case`.
- **Demo 2 (invalidate and close)**: finder submits report via inbox → vendor
  calls `POST .../trigger/invalidate-report` → vendor calls
  `POST .../trigger/close-report`.

Supporting changes:

- Added `post_to_trigger()` helper to `vultron/demo/utils.py`.
- Added `trigger` demo to `DEMOS` list in `vultron/demo/cli.py`; it now runs
  as part of `vultron-demo all`.
- Updated `docs/reference/code/demo/demos.md` and `cli.md` with new entries.

Phase PRIORITY-30 is now fully complete (P30-1 through P30-6).

---

## 2026-03-09 — ARCH-1.1 complete: MessageSemantics moved to vultron/core/models/events.py

Created `vultron/core/` package with `models/events.py` containing only
`MessageSemantics`. Removed the definition from `vultron/enums.py` (which
now re-exports it for backward compatibility). Updated all 17 direct import
sites across `vultron/` and `test/`. 815 tests pass.

The compatibility re-export in `vultron/enums.py` may be removed once ARCH-1.3
consolidates the extractor and the AS2 structural enums move to
`vultron/wire/as2/enums.py` (R-04).

---

## 2026-03-09 — ARCH-1.2 complete: InboundPayload introduced; AS2 type removed from DispatchActivity

Added `InboundPayload` to `vultron/core/models/events.py` with fields
`activity_id`, `actor_id`, `object_type`, `object_id`, and `raw_activity: Any`.
`DispatchActivity.payload` now types as `InboundPayload` instead of `as_Activity`,
removing the AS2 import from `vultron/types.py` (V-02) and from
`behavior_dispatcher.py` (V-03). All 38 handler functions updated to
`activity = dispatchable.payload.raw_activity`. `verify_semantics` decorator
updated to compare `dispatchable.semantic_type` directly (ARCH-07-001), removing
the second `find_matching_semantics` call. 815 tests pass.

---

## 2026-03-09 — ARCH-1.3 complete: wire/as2/parser.py and wire/as2/extractor.py created

### What moved

- **`vultron/wire/as2/parser.py`** (new): `parse_activity()` extracted from
  `vultron/api/v2/routers/actors.py`. Raises domain exceptions (`VultronParseError`
  hierarchy defined in `vultron/wire/as2/errors.py` and `vultron/wire/errors.py`)
  instead of `HTTPException`. The router now has a thin HTTP adapter wrapper that
  catches these and maps to 400/422 responses (R-03, V-06, ARCH-08-001).

- **`vultron/wire/as2/extractor.py`** (new): Consolidates `ActivityPattern` class,
  all 37 pattern instances, `SEMANTICS_ACTIVITY_PATTERNS` dict, and
  `find_matching_semantics()` from the former `vultron/activity_patterns.py` and
  `vultron/semantic_map.py`. This is now the sole location for AS2-to-domain
  semantic mapping (R-04, V-05, ARCH-03-001).

- **`vultron/wire/errors.py`** (new): `VultronWireError(VultronError)` base.
- **`vultron/wire/as2/errors.py`** (new): `VultronParseError`, subtypes for missing
  type, unknown type, and validation failure.

### Backward-compat shims retained

`vultron/activity_patterns.py` and `vultron/semantic_map.py` converted to
re-export shims so any external code importing from the old locations continues
to work. These can be deleted once confirmed no external callers remain.

### What else changed

- `vultron/behavior_dispatcher.py`: import `find_matching_semantics` from
  `vultron.wire.as2.extractor` (no longer `vultron.semantic_map`).
- `vultron/api/v2/backend/inbox_handler.py`: removed `raise_if_not_valid_activity`
  (V-07) and the `VOCABULARY` import; activity type validation now happens
  entirely in the wire parser layer before the item reaches the inbox handler.
- Tests: `test_raise_if_not_valid_activity_raises` deleted; 7 new wire layer tests
  added in `test/wire/as2/`. 822 tests pass (up from 815).

## 2026-03-10 — P60-2: vultron/behaviors/ moved to vultron/core/behaviors/

> ✅ Captured in `docs/adr/0009-hexagonal-architecture.md` (P60-2 marked
> complete) and `notes/codebase-structure.md`,
> `notes/architecture-ports-and-adapters.md`, `notes/bt-integration.md`
> (all updated 2026-03-10).

### What changed

- Copied entire `vultron/behaviors/` tree (bridge, helpers, case/, report/)
  to `vultron/core/behaviors/`.
- Updated all internal imports within the moved files from
  `vultron.behaviors.*` to `vultron.core.behaviors.*`.
- Updated all external callers:
  - `vultron/api/v2/backend/handlers/report.py` (lazy imports)
  - `vultron/api/v2/backend/handlers/case.py` (lazy imports)
  - `vultron/api/v2/backend/trigger_services/report.py`
  - 8 test files under `test/behaviors/`
- Deleted `vultron/behaviors/` entirely (no shim retained; all callers
  updated in the same step).
- 822 tests pass.

---

## TECHDEBT-9/7 — NonEmptyString type alias rollout (2026-03-10)

`NonEmptyString` and `OptionalNonEmptyString` were already defined in
`vultron/wire/as2/vocab/base/types.py` and partially applied. This task
completed the rollout across all remaining `Optional[str]` fields in
`vultron/wire/as2/vocab/objects/`:

- **`case_event.py`**: Replaced per-field `@field_validator` on `object_id`
  and `event_type` with `NonEmptyString` type annotations; removed validators.
- **`case_reference.py`**: Replaced per-field validators for `url` and `name`
  with `NonEmptyString` and `OptionalNonEmptyString`; removed validators.
- **`vulnerability_record.py`**: Changed `url: str | None` to
  `OptionalNonEmptyString`.
- **`case_participant.py`**: Changed `name` and `participant_case_name` from
  `str | None` to `OptionalNonEmptyString`.
- **`case_status.py`**: Changed `CaseStatus.context` and
  `ParticipantStatus.tracking_id` from `str | None` to `OptionalNonEmptyString`.

Error message updated: tests that previously asserted field-prefixed messages
(e.g., "object_id must be a non-empty string") now assert the shared message
"must be a non-empty string" (which the `AfterValidator` in `_non_empty` raises).

New tests added: `test_case_status.py`, extended `test_case_participant.py`,
extended `test_vulnerability_record.py`. 860 tests pass.

Note: `CaseParticipant.set_name_if_empty` model validator automatically
populates `name` from `attributed_to` when `name=None`; tests for `name=None`
must omit `attributed_to` to observe the None value.

## TECHDEBT-10 — Backfill pre-case events in create_case BT (2026-03-10)

**Task**: Backfill pre-case events into the case event log at case creation
(CM-02-009).

**Implementation**:

- Added `RecordCaseCreationEvents` node to
  `vultron/core/behaviors/case/nodes.py`. The node runs after `PersistCase` in
  the `CreateCaseFlow` sequence.
- The node records two events using `case.record_event()`:
  1. `"offer_received"` — only when the triggering activity has an
     `in_reply_to` reference (the originating Offer that led to case
     creation). The `object_id` is set to the Offer's `as_id`.
  2. `"case_created"` — always recorded; `object_id` is set to the case ID.
- The node reads `activity` from the global py_trees blackboard storage
  (`Blackboard.storage.get("/activity", None)`) rather than registering it as
  a required key. This avoids a `KeyError` when the tree is invoked without an
  inbound activity (e.g. in tests that pass `activity=None`).
- `create_tree.py` updated to import and include `RecordCaseCreationEvents` in
  the sequence.
- 6 new tests added to `test/core/behaviors/case/test_create_tree.py`.

**Key design note**: `received_at` in `CaseEvent` is set by
`default_factory=_now_utc`, satisfying CM-02-009's trusted-timestamp
requirement automatically. The node never copies a timestamp from the
incoming activity.

**866 tests pass.**

## TECHDEBT-8 — Pyright gradual static type checking (2026-03-10)

**Task**: Configure pyright for gradual static type checking (IMPL-TS-07-002).

**Implementation**:

- Added `pyright` to `[dependency-groups].dev` in `pyproject.toml`.
- Created `pyrightconfig.json` at the repo root with `typeCheckingMode: "basic"`,
  targeting `vultron/` and `test/`, Python 3.12, `reportMissingImports: true`,
  `reportMissingTypeStubs: false`.
- Added `pyright` target to `Makefile` (`uv run pyright`).

**Baseline error count (2026-03-10, pyright 1.1.408, basic mode)**:

```text
811 errors, 7 warnings, 0 informations
```

These errors are pre-existing technical debt and are NOT blocking. They will
be resolved incrementally as part of ongoing development. New and modified
code should be made clean under pyright basic mode before merging.

**Key error categories observed**:

- `reportInvalidTypeArguments`: `Optional[str]` spelled as `str | None` used
  as type argument (Pydantic `Annotated` patterns) — widespread across
  `wire/as2/vocab/objects/`.
- `reportAttributeAccessIssue` / `reportOptionalMemberAccess`: Union types
  narrowed incorrectly in property implementations.
- `reportGeneralTypeIssues`: Field override without default value.

---

## 2026-03-10 — P65-2 complete (marked; done in P65-1 commit)

P65-2 was implemented in the same commit as P65-1. The `inbox_handler.py`
already used `_DISPATCHER: ActivityDispatcher | None = None` at module level,
`init_dispatcher(dl)` for lifespan injection, and both `main.py` and `app.py`
call `init_dispatcher(dl=get_datalayer())` in their lifespan contexts.
No `get_datalayer()` call appears at module level or inside `dispatch()`.

## 2026-03-10 — P65-5 complete

### What was done

- Created `vultron/core/models/status.py` containing `ObjectStatus`,
  `OfferStatus`, `ReportStatus`, `STATUS`, `set_status`, `get_status_layer`,
  and `status_to_record_dict`. These were previously defined in the
  adapter-layer `api/v2/data/status.py`.
- Replaced `vultron/api/v2/data/status.py` with a backward-compat re-export
  shim pointing to `core/models/status`.
- Added `save_to_datalayer(dl, obj)` helper to `core/behaviors/helpers.py`.
  This constructs a `StorableRecord` from `obj.as_id`, `obj.as_type`, and
  `obj.model_dump(mode="json")` then calls `dl.update()`. Avoids importing
  the adapter-layer `Record`/`object_to_record` in core BT nodes.
- Updated `core/behaviors/report/nodes.py`: replaced `api/v2/data/status`
  and `api/v2/datalayer/db_record` imports with `core/models/status` and
  `core/behaviors/helpers`; replaced all `object_to_record` calls with
  `save_to_datalayer`; removed lazy imports at old lines 744–745.
- Updated `core/behaviors/case/nodes.py`: same pattern for `object_to_record`.

### What was NOT done (deferred to P65-6)

AS2 wire type imports (`VulnerabilityCase`, `CreateCase`, `CaseActor`,
`VendorParticipant`) remain in the core BT nodes — their removal requires
defining domain event types and an outbound serialiser (P65-6). The `ParticipantStatus`
lazy import was converted to a local import inside `_find_and_update_participant_rm`
(still a local import, but now the only remaining local import, and it
references a wire-layer type that will be addressed in P65-6).

### Violations addressed

- V-14 (Record): No core BT node imports `Record` or `object_to_record`.
- V-16: `core/behaviors/report/nodes.py` no longer imports `OfferStatus`
  from the adapter layer.
- V-18 partial: Adapter-level `object_to_record` removed from core BT nodes.

## P65-3: Enrich InboundPayload; Eliminate raw_activity

**Completed**: hexagonal-refactor branch

### Summary

Removed `raw_activity: Any` from `InboundPayload` (core domain type) and
replaced it with 13 typed domain fields (all `str | None`):
`activity_type`, `target_id`, `target_type`, `context_id`, `context_type`,
`origin_id`, `origin_type`, `inner_object_id`, `inner_object_type`,
`inner_target_id`, `inner_target_type`, `inner_context_id`, `inner_context_type`.

Added `wire_activity: Any` and `wire_object: Any` to `DispatchActivity` (adapter
layer) so handlers that persist AS2 objects can still do so without polluting the
core domain.

Added `extract_intent()` to `vultron/wire/as2/extractor.py` — the sole
AS2→domain mapping point — which returns `(MessageSemantics, InboundPayload)`
with all fields populated from the AS2 object graph.

Updated all 7 handler files (`report.py`, `case.py`, `actor.py`, `embargo.py`,
`note.py`, `participant.py`, `status.py`) to read exclusively from
`InboundPayload` fields and `dispatchable.wire_activity`/`wire_object`.

**Violations addressed**: V-02-R, V-11-R.  
**Result**: 880 tests pass, 0 regressions.

---

## P65-4 — Decouple `behavior_dispatcher.py` from the wire layer (2026-03-11)

Moved `prepare_for_dispatch()` from `vultron/behavior_dispatcher.py` to the
adapter layer (`vultron/api/v2/backend/inbox_handler.py`). The wire-layer
imports (`find_matching_semantics`, `extract_intent`) and the `Any` typing
import were removed from `behavior_dispatcher.py`. The `extract_intent` import
now lives in `inbox_handler.py`, the single adapter-layer entry point.

Moved the `test_prepare_for_dispatch_*` test from
`test/test_behavior_dispatcher.py` to
`test/api/v2/backend/test_inbox_handler.py` (adapter layer). Removed the
`as_Create` wire import and redundant `MessageSemantics = bd.MessageSemantics`
re-assignment from `test_behavior_dispatcher.py`.

**Violations addressed**: V-03-R.  
**Result**: 880 tests pass, 0 regressions.

---

## P65-6a — VultronEvent typed event hierarchy (2026-03-11)

**Task**: Define `VultronEvent` base class and per-semantic inbound domain event
subclasses in `core/models/events/`.

**What was done**:

- Converted `vultron/core/models/events.py` to a package (`events/`) with the
  following structure:
  - `base.py`: `MessageSemantics` enum, `NonEmptyString`/`OptionalNonEmptyString`
    helpers, and the `VultronEvent` Pydantic base class (same 17 fields as the
    former `InboundPayload` plus the required `semantic_type: MessageSemantics`
    discriminator field).
  - `report.py`, `case.py`, `actor.py`, `case_participant.py`, `embargo.py`,
    `note.py`, `status.py`, `unknown.py`: per-semantic `FooReceivedEvent`
    subclasses, each setting `semantic_type: Literal[MessageSemantics.X]`.
    Covers all 38 semantics + `UNKNOWN`.
  - `__init__.py`: exports all types, `EVENT_CLASS_MAP` (dict mapping each
    `MessageSemantics` to its concrete class), and the backward-compat alias
    `InboundPayload = VultronEvent`.
- Updated `extract_intent()` in `wire/as2/extractor.py` to return a single
  typed `VultronEvent` subclass (not a `(MessageSemantics, InboundPayload)`
  tuple). Uses `EVENT_CLASS_MAP` to construct the correct subclass.
- Updated `DispatchActivity.payload` type in `vultron/types.py` from
  `InboundPayload` to `VultronEvent`.
- Updated `prepare_for_dispatch()` in `inbox_handler.py` to unpack
  `event = extract_intent(activity)` and read `event.semantic_type`.
- Removed redundant `object_type` string guards from `create_report`,
  `submit_report`, and `validate_report` handlers (guaranteed by semantic
  pattern matching).
- Updated `test_behavior_dispatcher.py` to use `CreateReportReceivedEvent`
  instead of `InboundPayload`.
- Updated `_make_payload` in `test_handlers.py` to auto-derive `semantic_type`
  via `find_matching_semantics()` and return the correctly typed subclass via
  `EVENT_CLASS_MAP`.
- Updated `_call_handler` in `test_reporting_workflow.py` to use the new
  single-value `extract_intent()` return.

**Violations addressed**: V-02-R follow-on (typed domain events replace generic
payload; extractor now returns discriminated subclasses).

**Result**: 880 tests pass, 0 regressions.

---

## P65-6b — Remove AS2 wire imports from core/behaviors/ (R-09 part 2)

**Files created**:

- `vultron/core/models/vultron_types.py`: Rich domain types — `VultronCase`,
  `VultronReport`, `VultronCaseActor`, `VultronParticipant`,
  `VultronCreateCaseActivity`, `VultronParticipantStatus`, `VultronCaseStatus`,
  `VultronCaseEvent`. Each mirrors the Vultron-specific fields of its wire
  counterpart, using `str` IDs for cross-references and clean Python enums.
  `as_type` strings match wire values for DataLayer round-trip compatibility.
- `vultron/wire/as2/serializer.py`: Outbound serializer converting domain →
  wire types for adapter-layer use. Core BT nodes do NOT import this.

**Files modified**:

- `vultron/core/behaviors/case/nodes.py`: Wire imports replaced with domain
  types; `CVDRoles.VENDOR` role set explicitly on `VultronParticipant`.
- `vultron/core/behaviors/case/create_tree.py`: `VulnerabilityCase` →
  `VultronCase` type annotation.
- `vultron/core/behaviors/report/nodes.py`: Wire imports replaced; field name
  `actor` → `attributed_to` in `VultronParticipantStatus` construction.
- `vultron/core/behaviors/report/policy.py`: Wire imports fully replaced with
  `VultronCase`/`VultronReport`.

**Key decisions**:

- Domain types are rich (mirror Vultron-specific fields), not thin stubs.
- `CVDRoles` serialization uses `@field_serializer` returning `.name` strings,
  matching the wire `CaseParticipant` convention.
- `VultronParticipantStatus` appended to wire `CaseParticipant.participant_statuses`
  works via Pydantic v2 duck-typing (list.append bypasses field validation;
  round-trip through `model_dump(mode="json")` + `model_validate` succeeds).
- `_now_utc()` uses stdlib `datetime.now(timezone.utc)` to avoid importing
  `now_utc` from the wire layer.

**Violations addressed**: V-15 (full), V-17, V-18 (full), V-19.

**Result**: 880 tests pass, 0 regressions.

---

## P65-7 — Remove wire AS2 imports from core BT test files (commit 59e85ca)

**Goal**: No `core/behaviors/` test file imports wire-layer AS2 types.

**Changes**:

- `vultron/core/models/vultron_types.py`: Added `VultronOffer`, `VultronAccept`,
  `VultronOutbox` domain types. Added `outbox: VultronOutbox` field to
  `VultronCaseActor` (required for `UpdateActorOutbox` BT node's
  `save_to_datalayer` call). Widened `VultronCase.case_participants` to
  `list[str | VultronParticipant]`.
- `test/core/behaviors/report/test_nodes.py`: Replaced `as_Service`,
  `VulnerabilityReport`, `as_Offer` with domain equivalents.
- `test/core/behaviors/report/test_validate_tree.py`: Same substitutions.
- `test/core/behaviors/report/test_prioritize_tree.py`: Replaced
  `VulnerabilityCase`, `CaseParticipant`, `VulnerabilityReport`, `as_Service`.
- `test/core/behaviors/case/test_create_tree.py`: Replaced all wire imports;
  removed unused `CaseActor`/`VendorParticipant` imports.
- `test/core/behaviors/test_performance.py`: Replaced all top-level wire
  imports; `mock_read` returns `VultronCaseActor` for actor IDs (previously
  `MagicMock`, which broke `model_dump()` in `save_to_datalayer`).

**Violations addressed**: V-22 (partial → complete resolution pending P65-4),
V-23 (full).

**Result**: 880 tests pass, 0 regressions.

---

## ARCH-DOCS-1 — Update architecture-review.md violation status markers

**Date**: 2026-03-11
**Commit**: d19252a

Updated `notes/architecture-review.md` to accurately reflect the post-P65-7
state of the codebase. All violations V-01 through V-23 are now marked as
fully resolved.

**Changes made**:

- Status header block: added new paragraph summarising P65-4, P65-6b, and P65-7
  completions; declared all V-01–V-23 resolved.
- Section headers for "Active Regressions" and "New Violations" updated with
  "All Resolved ✅" suffixes.
- V-03-R: heading updated to ✅ RESOLVED (P65-4); body replaced plan text with
  what was done.
- V-15, V-16, V-18: heading updated from ⚠️ PARTIALLY RESOLVED to ✅ RESOLVED
  (P65-6b); full resolution text appended.
- V-17, V-19: heading updated to ✅ RESOLVED (P65-6b); resolution text added.
- V-22, V-23: heading updated to ✅ RESOLVED (P65-7); resolution text added.
- R-09: updated from ⚠️ PARTIALLY COMPLETE to ✅ COMPLETE; replaced remaining
  work list with what-was-done summary.
- R-10: updated to ✅ COMPLETE; replaced plan text with outcome summary.
- R-11: updated to ✅ COMPLETE inline (previously had no status marker).

**Result**: 880 tests pass, 0 regressions. No code changes — documentation only.

---

## TECHDEBT-13a — Wire-boundary cleanup: test_policy.py (COMPLETE 2026-03-11)

Replaced `VulnerabilityReport` import (from `vultron.wire.as2.vocab.objects`)
with `VultronReport` (from `vultron.core.models.vultron_types`) in
`test/core/behaviors/report/test_policy.py`. This eliminates the residual V-23
violation where a core-layer test imported a wire-layer type. Tests pass via
duck-typing since `VultronReport` has the same fields (`as_id`, `name`,
`content`) as the wire-layer type the policy module already expects.

**Result**: 880 tests pass, 0 regressions. No production code changes.

---

## TECHDEBT-13b/c — Wire-boundary cleanup: _base.py and TYPE_CHECKING imports (COMPLETE 2026-03-11)

**TECHDEBT-13b**: Updated `vultron/wire/as2/vocab/examples/_base.py` to remove
all adapter-layer imports. The module-level `DataLayer` annotation now imports
from `vultron.core.ports.activity_store`; `initialize_examples()` requires an
explicit `DataLayer` argument (removed `None` default, `get_datalayer()`
fallback, and `Record.from_obj()` usage). Objects are passed directly to
`datalayer.create()` since the `DataLayer` protocol accepts `BaseModel`.

**TECHDEBT-13c**: Updated `TYPE_CHECKING` guard imports in `vultron/types.py`
and `vultron/behavior_dispatcher.py` to reference
`vultron.core.ports.activity_store.DataLayer` directly instead of the
`vultron.api.v2.datalayer.abc` shim.

**Result**: 880 tests pass, 0 regressions. V-24 fully resolved.

---

## P70-3 — Add core/ports/delivery_queue.py and dns_resolver.py Protocol stubs (COMPLETE 2026-03-11)

Added two Protocol stub files to `vultron/core/ports/`:

- **`delivery_queue.py`**: `DeliveryQueue` Protocol with `enqueue(activity_id, recipient_id) -> None`
  and `drain() -> int`. Mirrors the outbound delivery contract referenced by
  `vultron/adapters/driven/delivery_queue.py`.
- **`dns_resolver.py`**: `DnsResolver` Protocol with `resolve_txt(domain) -> list[str]`.
  Mirrors the trust-discovery contract referenced by
  `vultron/adapters/driven/dns_resolver.py`.

Both files contain only `Protocol` class definitions with no adapter-layer imports,
following the pattern established by `vultron/core/ports/activity_store.py`.

**Result**: 880 tests pass, 0 regressions. Both driven adapter stubs import cleanly.

---

## P70-2 — Relocate OfferStatusEnum and VultronObjectType to core (COMPLETE 2026-03-11)

Moved both domain-boundary enums out of `vultron/enums.py` into their correct
architectural homes and deleted the now-empty shim:

- **`OfferStatusEnum`** → `vultron/core/models/status.py` (defined before
  `ObjectStatus` which uses it; removed separate import)
- **`VultronObjectType`** → new `vultron/core/models/enums.py` (wire layer
  must import from core, not define its own parallel enum)
- **`vultron/enums.py`** deleted (all three symbols now imported directly from
  their canonical locations; `MessageSemantics` was already imported directly
  from `vultron.core.models.events` by all callers)

Updated 13 caller files across `vultron/wire/as2/`, `vultron/api/v2/`,
`vultron/core/`, and `test/`.

**Result**: 880 tests pass, 0 regressions. No `vultron.enums` imports remain.

---

## P70-4 — Move TinyDbDataLayer to adapters/driven/ (2026-03-11)

**Task**: Move `vultron/api/v2/datalayer/tinydb_backend.py` (the TinyDB
implementation) to `vultron/adapters/driven/activity_store.py` and leave
a backward-compat re-export shim at the old path.

**What was done**:

- Populated `vultron/adapters/driven/activity_store.py` (formerly a stub
  docstring) with the full `TinyDbDataLayer` class, `get_datalayer()`, and
  `reset_datalayer()`. Updated the `DataLayer` import to reference
  `vultron.core.ports.activity_store` directly instead of the `abc.py` shim.
- Replaced `vultron/api/v2/datalayer/tinydb_backend.py` with a one-file
  backward-compat shim that re-exports `TinyDbDataLayer`, `get_datalayer`,
  and `reset_datalayer` from `vultron.adapters.driven.activity_store`.
- All existing callers of the old path continue to work via the shim; no
  other files were modified.

**Result**: 880 tests pass, 0 regressions.

**Next**: P70-5 — remove shims and update all remaining callers to import
from `adapters/driven/` directly.

---

### P70-5 — Remove DataLayer shims (2026-03-12)

**Task**: Remove backward-compat shims `api/v2/datalayer/abc.py`,
`api/v2/datalayer/tinydb_backend.py`, and `api/v2/datalayer/db_record.py`;
update all callers to import from canonical locations.

**What was done**:

- Moved `vultron/api/v2/datalayer/db_record.py` to
  `vultron/adapters/driven/db_record.py`.
- Updated `vultron/adapters/driven/datalayer_tinydb.py` to import `Record`,
  `object_to_record`, and `record_to_object` from the new local path.
- Bulk-updated all `vultron/` and `test/` files (≈50 files) with `sed`:
  - `vultron.api.v2.datalayer.abc.DataLayer` → `vultron.core.ports.datalayer.DataLayer`
  - `vultron.api.v2.datalayer.tinydb_backend.*` → `vultron.adapters.driven.datalayer_tinydb.*`
  - `vultron.api.v2.datalayer.db_record.*` → `vultron.adapters.driven.db_record.*`
- Deleted `abc.py`, `tinydb_backend.py`, and `db_record.py` from
  `vultron/api/v2/datalayer/`.
- No module now imports from `vultron.api.v2.datalayer.*`.

**Result**: 880 tests pass, 0 regressions.

**Next**: P75-1 — define `VultronEvent` domain event types in `core/models/events.py`.

---

## P75-1 — VultronEvent domain event types (verified complete 2026-03-12)

**Task**: Define `VultronEvent` domain event base type and all 38 per-semantic
concrete subclasses in `vultron/core/models/events/`, with no wire or adapter
imports.

**What was done** (completed as part of P65-6a, verified now):

- `vultron/core/models/events/` package exists with:
  - `base.py`: `MessageSemantics` (39 values), `VultronEvent` base class,
    `NonEmptyString`, `OptionalNonEmptyString`
  - Per-category modules: `actor.py`, `case.py`, `case_participant.py`,
    `embargo.py`, `note.py`, `report.py`, `status.py`, `unknown.py`
  - `__init__.py`: `EVENT_CLASS_MAP` (all 39 semantics mapped), `InboundPayload`
    backward-compat alias for `VultronEvent`
- No wire-layer or adapter-layer imports anywhere in `core/models/events/`
- All 39 `MessageSemantics` values covered by the `EVENT_CLASS_MAP`

**Result**: 880 tests pass, 0 regressions.

**Next**: P75-2 — extract handler business logic from
`vultron/api/v2/backend/handlers/` into `vultron/core/use_cases/`.

---

## P75-2 — Extract Handler Business Logic to Core Use Cases

**Completed**: 2026-03-13

**What was done**: Extracted all 38 handler functions from
`vultron/api/v2/backend/handlers/` into 8 new use-case modules under
`vultron/core/use_cases/`. Handlers are now thin delegates that call
`uc.func(dispatchable.payload, dl)`.

**Supporting changes**:

- Added `VultronActivity`, `VultronNote`, `VultronEmbargoEvent` domain
  types to `vultron/core/models/vultron_types.py`
- Enriched all `VultronEvent` subclasses with optional typed domain-object
  fields (`report`, `case`, `embargo`, `note`, `participant`, `activity`,
  `status`) populated by `extract_intent()` in the wire layer
- Added `in_reply_to` field and `as_id` property to `VultronEvent` base
  (BT bridge nodes read `activity.as_id` and `activity.in_reply_to`)
- Added `DataLayer.save(obj: BaseModel)` port method (upsert semantics)
  implemented by `TinyDbDataLayer`; use cases call `dl.save()` instead of
  `dl.update(id, object_to_record(obj))`
- Added `CaseModel` and `ParticipantModel` Protocols in
  `vultron/core/use_cases/_types.py` for type-safe duck-typed access to
  DataLayer results
- Use cases call `dl.read()` instead of `rehydrate()` for object loading;
  handlers pass `wire_object`/`wire_activity` as optional kwargs where
  DataLayer round-trip would lose wire subtype information

**Result**: 880 tests pass, 0 regressions.

**Next**: P75-3 — migrate trigger-service logic to `vultron/core/use_cases/`.

---

## P75-2a — Core Domain Model Audit and Enrichment (2026-03-13)

**Task**: Audit every `Vultron*` domain type in `vultron/core/models/vultron_types.py`
against its wire counterpart, add missing semantically relevant fields, update
`extract_intent()` to populate them, and add round-trip tests.

**Fields added per domain type**:

- `VultronCaseStatus`: `name`
- `VultronParticipantStatus`: `name`, `case_status` (case status ID ref); `vfd_state`
  was already present in the domain model but not populated by `extract_intent()` —
  that gap was also fixed.
- `VultronReport`: `summary`, `url`, `media_type`, `published`, `updated`
- `VultronCase`: `url`, `published`, `updated`
- `VultronActivity`: `origin`
- `VultronNote`: `summary`, `url`
- `VultronEmbargoEvent`: `published`, `updated`

**extract_intent() changes**: All new fields are now populated. Additionally,
`VultronParticipant` extraction was extended to populate `case_roles` and
`participant_case_name` from the incoming wire `CaseParticipant` (these fields were
already in the domain model but not wired up). `VultronActivity.origin` is now
populated from the wire activity's `origin` field.

**Tests**: 8 new tests added to `test/wire/as2/test_extractor.py` verifying
wire-to-domain round-trips for each new field category.

**Intentionally excluded** (AS2 boilerplate not relevant for domain logic):
`as_context`, `preview`, `replies`, `generator`, `icon`, `image`, `attachment`,
`location`, `to`, `cc`, `bto`, `bcc`, `audience`, `duration`, `tag`, `in_reply_to`
(except where already present), `instrument`, `result`.

**Result**: 888 tests pass (880 prior + 8 new), 0 regressions.

**Next**: P75-2b — remove wire coupling from dispatch envelope, rename
`DispatchActivity` → `DispatchEvent`.

---

## P75-2b — Remove wire coupling from dispatch envelope (2026-03-13)

**Task**: Rename `DispatchActivity` → `DispatchEvent`, remove `wire_activity`
and `wire_object` fields from the dispatch envelope, and eliminate wire-object
pass-through parameters from all use case functions.

**Changes**:

- `vultron/types.py`: Renamed `DispatchActivity` → `DispatchEvent`, removed
  `wire_activity: Any` and `wire_object: Any` fields, removed
  `ConfigDict(arbitrary_types_allowed=True)`, updated `BehaviorHandler`
  Protocol; added backward-compat alias `DispatchActivity = DispatchEvent`.
- `vultron/behavior_dispatcher.py`: Updated 3 references.
- `vultron/api/v2/backend/inbox_handler.py`: Removed `wire_object` extraction,
  updated `DispatchEvent()` constructor.
- All 8 handler files: Updated imports and annotations.
- All 6 use case files: Removed `wire_object`/`wire_activity` params; replaced
  fallback logic with direct `event.X` access.
- `vultron/wire/as2/extractor.py`: Fixed `isinstance(obj, WireType)` checks
  in `_build_domain_kwargs()` — replaced with `as_type` string comparisons
  (`_obj_type == str(VOtype.X)`) because the wire parser deserializes nested
  objects as `as_Object` base class, causing `isinstance` checks against
  Vultron subtypes to always fail.
- `vultron/core/use_cases/status.py`: Fixed `add_case_status_to_case` and
  `add_participant_status_to_participant` to fall back to `event.status` when
  `dl.read(status_id)` returns a non-model (raw TinyDB Document).
- `vultron/core/models/vultron_types.py`: Added `field_serializer` for
  `pxa_state` on `VultronCaseStatus` and `vfd_state` on
  `VultronParticipantStatus` to serialize as `.name` strings (matching wire
  type serialization), fixing `[0,0,0]` round-trip failures.
- Test files: Updated for `DispatchEvent` rename.
- `specs/dispatch-routing.md`, `specs/handler-protocol.md`,
  `specs/code-style.md`, `specs/architecture.md`, `specs/README.md`,
  `AGENTS.md`, `docs/adr/0009-hexagonal-architecture.md`,
  `docs/reference/inbox_handler.md`: Updated `DispatchActivity` → `DispatchEvent`.

**Result**: 888 tests pass, 0 regressions.

**Next**: P75-2c — model dispatcher as formal driving port.

## TECHDEBT-14 — Split vultron_types.py into per-type modules

**Completed**: 2026-03-13

Split `vultron/core/models/vultron_types.py` (273 lines, 11 classes) into
individual per-type modules following the `wire/as2/vocab/objects/` pattern:

- `_helpers.py` — shared `_now_utc` / `_new_urn` factory functions
- `case_event.py` — `VultronCaseEvent`
- `case_status.py` — `VultronCaseStatus`
- `participant_status.py` — `VultronParticipantStatus`
- `participant.py` — `VultronParticipant`
- `case_actor.py` — `VultronCaseActor`, `VultronOutbox`
- `activity.py` — `VultronActivity`, `VultronOffer`, `VultronAccept`, `VultronCreateCaseActivity`
- `report.py` — `VultronReport`
- `case.py` — `VultronCase`
- `note.py` — `VultronNote`
- `embargo_event.py` — `VultronEmbargoEvent`

`vultron_types.py` retained as a backward-compatibility re-export shim.
All existing callers continue to work without modification. 887 tests pass.

Note: `test_remove_embargo` is a pre-existing flaky test (py_trees blackboard
global state) that passes in isolation but occasionally fails in full suite.

## P75-2c — Dispatcher driving port, flatten handler layer, rename patterns

**Status:** Complete  
**Branch:** `hexagonal-refactor`

### Summary

Completed the P75-2c architectural task: modelled the dispatcher as a formal
driving port, flattened the handler adapter layer, and renamed all
`ActivityPattern` instances with a `Pattern` suffix.

### Files Created

- `vultron/core/ports/dispatcher.py` — `ActivityDispatcher` Protocol with
  `dispatch(event: VultronEvent, dl: DataLayer) -> None` signature
- `vultron/core/use_cases/use_case_map.py` — `USE_CASE_MAP` authoritative
  routing table mapping all 39 `MessageSemantics` → use-case callables
- `vultron/core/dispatcher.py` — `DispatcherBase`, `DirectActivityDispatcher`,
  `get_dispatcher` factory (dl passed at dispatch time, not construction time)
- `vultron/api/v2/backend/handlers/_shim.py` — no-op `verify_semantics`
  backward-compat stub

### Files Modified

- `vultron/behavior_dispatcher.py` — backward-compat shim re-exporting from
  `vultron.core.dispatcher` and `vultron.core.ports.dispatcher`
- `vultron/api/v2/backend/handler_map.py` — re-exports `USE_CASE_MAP` as
  `SEMANTICS_HANDLERS` alias
- `vultron/api/v2/backend/inbox_handler.py` — updated to new dispatch signature
  (`dispatch(event, dl)`, `handle_inbox_item(actor_id, obj, dl)`)
- `vultron/api/v2/backend/handlers/__init__.py` — shim wrappers that unwrap
  `DispatchEvent` and delegate to core use cases (backward compat for tests)
- `vultron/wire/as2/extractor.py` — all `ActivityPattern` instances renamed
  with `Pattern` suffix
- `vultron/types.py` — updated `BehaviorHandler` Protocol signature
- `AGENTS.md` — updated quickstart, pipeline description, Registry Pattern,
  Use-Case Protocol, Adding a New Message Type, and Key Files Map sections
- `test/test_behavior_dispatcher.py` — updated for new dispatcher API
- `test/api/v2/backend/test_inbox_handler.py` — updated for new `handle_inbox_item` API
- `test/api/v2/backend/test_handlers.py` — updated `TestVerifySemanticsDecorator`
  to reflect no-op decorator; updated `TestHandlerExecution` to drop removed
  mismatch-raise test

### Files Deleted

Nine handler shim modules removed (logic now lives in `core/use_cases/`):
`handlers/report.py`, `handlers/case.py`, `handlers/embargo.py`,
`handlers/actor.py`, `handlers/note.py`, `handlers/status.py`,
`handlers/unknown.py`, `handlers/_base.py`, `handlers/participant.py`

### Test Result

887 passed, 0 failed (pre-existing flaky `test_remove_embargo` passed this run)

---

## P75-3: Migrate trigger-service logic to core use cases

**Completed:** 2026

**Summary:** Moved all domain logic from `vultron/api/v2/backend/trigger_services/`
into `vultron/core/use_cases/triggers/`. The adapter layer is now reduced to thin
delegates that translate domain exceptions to `HTTPException`.

**Files created:**

- `vultron/core/use_cases/triggers/__init__.py` — exports all 9 `svc_*` functions
- `vultron/core/use_cases/triggers/_helpers.py` — domain helpers (resolve_actor,
  resolve_case, update_participant_rm_state, add_activity_to_outbox, outbox_ids,
  find_embargo_proposal) — raises domain exceptions, no FastAPI
- `vultron/core/use_cases/triggers/report.py` — svc_validate_report, svc_invalidate_report,
  svc_reject_report, svc_close_report
- `vultron/core/use_cases/triggers/case.py` — svc_engage_case, svc_defer_case
- `vultron/core/use_cases/triggers/embargo.py` — svc_propose_embargo, svc_evaluate_embargo,
  svc_terminate_embargo

**Files modified (reduced to thin delegates):**

- `vultron/api/v2/backend/trigger_services/_helpers.py` — HTTP error translation +
  re-exports from core helpers
- `vultron/api/v2/backend/trigger_services/report.py` — thin delegate
- `vultron/api/v2/backend/trigger_services/case.py` — thin delegate
- `vultron/api/v2/backend/trigger_services/embargo.py` — thin delegate
- `vultron/errors.py` — added VultronNotFoundError, VultronConflictError,
  VultronValidationError

**Domain exceptions added:** `VultronNotFoundError` (→ HTTP 404),
`VultronConflictError` (→ HTTP 409), `VultronValidationError` (→ HTTP 422)

**Test results:** 887 passed, 0 failed

---

## P75-4-pre — Standardize UseCase Interface (2026-03-16)

**What was done:**

- Created `vultron/core/ports/use_case.py` — defines the `UseCase[Req, Res]`
  Protocol with a single `execute(request: Req) -> Res` method.  This is the
  standard interface all class-based use cases must implement going forward.
- Refactored `vultron/core/use_cases/unknown.py` — introduced `UnknownUseCase`
  as the reference implementation (`__init__` receives `DataLayer`; `execute`
  contains the logic).  The old `unknown(event, dl)` function is kept as a
  thin backward-compat wrapper so the existing dispatcher routing table and
  tests are unaffected.
- Added `test/core/ports/` package with `test_use_case.py` — 8 new tests
  covering Protocol structural check, `UnknownUseCase` construction, logging
  behaviour, and backward-compat wrapper.

**Test results:** 895 passed, 0 failed

---

## TECHDEBT-15 — Fix flaky `test_remove_embargo` test (2026-03-16)

**Task**: Add `autouse` fixture to `test/wire/as2/vocab/conftest.py` to clear
the py_trees blackboard global state before and after each test in that
directory (TB-06-006, AGENTS.md "py_trees Blackboard Global State").

**What was done:**

- Created `test/wire/as2/vocab/conftest.py` with a `clear_py_trees_blackboard`
  `autouse` fixture that calls `py_trees.blackboard.Blackboard.storage.clear()`
  before and after each test function, matching the pattern in
  `test/core/behaviors/conftest.py`.
- Verified `test_remove_embargo` passes reliably across 5 consecutive runs.
- Full test suite continues to pass (895 tests).

**Test results:** 895 passed, 0 failed

---

## P75-4 — UseCase class interface + CLI/MCP driving adapters (2026-03-16)

**Task**: Convert all 38 handler use cases and 9 trigger use cases from
old-style `fn(event, dl)` callables to the `UseCase[Req, Res]` class
interface defined in P75-4-pre. Implement functional CLI and MCP driving
adapters that exercise the same code paths as the HTTP inbox adapter.

**What was done:**

- Converted all 38 handler use cases across `report.py`, `case.py`,
  `actor.py`, `embargo.py`, `case_participant.py`, `note.py`, `status.py`
  to `XxxUseCase` classes: `__init__(self, dl: DataLayer)` + `execute(self, request) -> None`.
- Converted all 9 trigger use cases across `triggers/report.py`,
  `triggers/case.py`, `triggers/embargo.py` to `SvcXxxUseCase` classes.
- Added `vultron/core/use_cases/triggers/requests.py` with 9 Pydantic
  domain request models (include `actor_id`) for trigger use cases.
- Updated `USE_CASE_MAP` to map `MessageSemantics → class` (not callable).
- Updated `vultron/core/dispatcher.py`: `_handle` now calls
  `use_case_class(dl).execute(event)` — DataLayer injected at construction.
- Updated trigger service adapter shims to instantiate classes and build
  domain request models; HTTP router signatures unchanged.
- Removed the temporary `unknown()` callable wrapper (now obsolete).
- Implemented `vultron/adapters/driving/cli.py`: functional `click` CLI
  (`vultron-cli deliver ACTOR_ID`) reusing the same
  parse→rehydrate→dispatch pipeline as the HTTP inbox with injected DataLayer.
- Implemented `vultron/adapters/driving/mcp_server.py`: 9 MCP tool
  functions + `MCP_TOOLS` list, ready for MCP SDK registration (Priority 1000).

**Test results:** 893 passed, 0 failed (2 fewer than baseline: `TestUnknownFunction`
tests for the removed `unknown()` wrapper were intentionally deleted).

## TECHDEBT-17, TECHDEBT-18, TECHDEBT-20 — Batch 80a: Dead code removal (2026-03-16)

**Tasks**: TECHDEBT-17, TECHDEBT-18, TECHDEBT-20

- **TECHDEBT-17**: Deleted 279 lines of pre-refactor bare function stubs
  (`create_embargo_event`, `add_embargo_event_to_case`,
  `remove_embargo_event_from_case`, `announce_embargo_event_to_case`,
  `invite_to_embargo_on_case`, `accept_invite_to_embargo_on_case`,
  `reject_invite_to_embargo_on_case`) from `vultron/core/use_cases/embargo.py`
  that duplicated the class-based use cases above them and were not called
  anywhere (shim layer already delegated to class-based versions).
- **TECHDEBT-18**: Deleted 53 lines — a duplicate import block and second
  definition of `_resolve_offer_and_report` from
  `vultron/core/use_cases/triggers/report.py` (block starting with bare
  `import logging` after `SvcCloseReportUseCase`).
- **TECHDEBT-20**: Deleted 25 lines — a duplicate import block ending with
  `logger = logging.getLogger(__name__)` from
  `vultron/core/use_cases/triggers/embargo.py` (block after
  `SvcTerminateEmbargoUseCase`).

**Test results:** 893 passed, 0 failed (unchanged from baseline).

---

### TECHDEBT-19 + TECHDEBT-24 (partial) — Remove api.v2.* and wire-layer imports from core (2026-03-16)

**Task**: TECHDEBT-19 (Batch 80b) + partial TECHDEBT-24.

**What was done**:

- Moved `rehydrate` from `vultron/api/v2/data/rehydration.py` to
  `vultron/wire/as2/rehydration.py`. Added `dl: DataLayer | None = None`
  parameter so callers with a DataLayer in scope can pass it directly (avoiding
  the adapter-layer `get_datalayer()` fallback). Module-level import of
  `get_datalayer` enables monkeypatching in tests. Deleted the old
  `api/v2/data/rehydration.py` file entirely (no shim — see `plan/IDEAS.md`).
  Updated all callers (`inbox_handler.py`, `cli.py`, `routers/datalayer.py`,
  `triggers/report.py`, and ~25 test patches) to import from the new location.
- Updated `triggers/report.py` status imports from `vultron.api.v2.data.status`
  to `vultron.core.models.status` (the authoritative location; `api.v2.data.status`
  was already a re-export shim).
- Partial TECHDEBT-24 (`triggers/_helpers.py`): Removed `VulnerabilityCase` and
  `ParticipantStatus` imports from `triggers/_helpers.py`. Changed
  `resolve_case` return type to `CaseModel` (Protocol). Added
  `append_rm_state(rm_state, actor, context)` method to `CaseParticipant` (wire)
  and `ParticipantModel` (Protocol in `_types.py`), eliminating the need to
  instantiate `ParticipantStatus` in the helper.
- TECHDEBT-24 `case.py` deferred: Passing `VultronCase` directly to
  `create_create_case_tree` caused `VulnerabilityCase.current_status` to fail
  with `max() iterable argument is empty` after a TinyDB round-trip because
  `VultronCase` initialises `case_statuses = []` while `VulnerabilityCase` uses
  `default_factory=init_case_status` to produce `[CaseStatus()]`. The lazy
  `VulnerabilityCase` import in `case.py` was retained; see TECHDEBT-24
  remaining item in the plan for the options.

**Test results:** 893 passed, 0 failed (unchanged from baseline).

---

## TECHDEBT-21 — Rename handler use cases with `Received` suffix (2026-03-16)

**Task**: Per CS-12-002, all handler use case classes (those that process
received ActivityStreams messages) should carry a `Received` suffix to
distinguish them from trigger (Svc-prefixed) use cases.

**What was done**:

- Renamed all 38 handler use case classes across 7 source files in
  `vultron/core/use_cases/` to insert `Received` before `UseCase`
  (e.g., `CreateReportUseCase` → `CreateReportReceivedUseCase`).
- Updated `USE_CASE_MAP` in `core/use_cases/use_case_map.py` (38 entries).
- Updated the shim layer in `vultron/api/v2/backend/handlers/__init__.py`
  (38 call sites).
- Pure mechanical rename; no logic changes.

**Test results:** 893 passed, 0 failed (unchanged from baseline).

---

## TECHDEBT-24 (remaining) — Remove wire-layer import from `core/use_cases/case.py`

**Date**: 2026-03-16
**Task**: Remove lazy `VulnerabilityCase` import from `CreateCaseReceivedUseCase.execute`

**What was done**:

- In `vultron/core/models/case.py`: changed `VultronCase.case_statuses`
  `default_factory` from `list` (empty) to `lambda: [VultronCaseStatus()]`,
  giving the domain model the same initial case status as
  `VulnerabilityCase.init_case_status()`. This ensures that when a `VultronCase`
  is stored in TinyDB and subsequently read back as a `VulnerabilityCase`, the
  `case_statuses` list is non-empty and `VulnerabilityCase.current_status`
  (`max()`) does not raise `ValueError`.
- In `vultron/core/use_cases/case.py`: removed the lazy `from vultron.wire…
  import VulnerabilityCase` and the intermediate `case_wire = VulnerabilityCase(…)`
  construction from `CreateCaseReceivedUseCase.execute`. The `VultronCase`
  already present on `request.case` is now passed directly to
  `create_create_case_tree`. `case.py` has no imports from `vultron.wire.*`.

**Lessons learned**: Enriching the domain model (option a) is architecturally
preferable to guarding symptoms in the wire type. The domain object should
always initialise to a valid state.

**Test results:** 893 passed, 0 failed (unchanged from baseline).

---

## TECHDEBT-22 — UseCase[Req, Res] Protocol base on all use case classes (2026-03-16)

**What was done**: Added explicit `UseCase[RequestType, ResponseType]` inheritance
to all 47 use case classes across 11 files in `core/use_cases/` and
`core/use_cases/triggers/`. Handler use cases inherit from
`UseCase[XxxReceivedEvent, None]`; trigger use cases inherit from
`UseCase[XxxTriggerRequest, dict]`. Added `from vultron.core.ports.use_case
import UseCase` import to each file. Fixed two edge cases where the import
insertion script placed the new import inside a multi-line import block in
`triggers/case.py` and `triggers/report.py`.

**Lessons learned**: When inserting imports after the last import line, a line
scan looking for `from` / `import` prefixes can land on the first line of a
multi-line import block. Must verify the located line is not inside an unclosed
parenthesis.

**Test results:** 893 passed, 0 failed (unchanged from baseline).

---

## Batch 80e — TECHDEBT-23 + TECHDEBT-25 + TECHDEBT-26 + TECHDEBT-28 (2026-03-16)

**Tasks completed**: TECHDEBT-23, TECHDEBT-25, TECHDEBT-26, TECHDEBT-28

### What was done

**TECHDEBT-23** — Added `TriggerRequest` base class in
`vultron/core/use_cases/triggers/requests.py` with shared `model_config` and
`actor_id: NonEmptyString`. All 9 concrete trigger request models now inherit
from `TriggerRequest` with duplicate `model_config` and `actor_id` fields
removed.

**TECHDEBT-25** — Created `vultron/core/use_cases/_helpers.py` with
`_as_id(obj) -> str | None` helper that normalises mixed `str | wire-object`
values to a plain string ID. Replaced ~15 scattered `obj.as_id if hasattr(...)`
ternary patterns across `case.py`, `actor.py`, `embargo.py`,
`case_participant.py`, `note.py`, and `status.py`.

**TECHDEBT-26** — Removed the `OptionalNonEmptyString` type alias from both
definition sites (`wire/as2/vocab/base/types.py` and
`core/models/events/base.py`) and all usage sites (5 wire-layer vocab objects,
`core/models/events/base.py`). Replaced with the inline `NonEmptyString | None`
form. Removed the re-export from `core/models/events/__init__.py`. Updated
`specs/code-style.md` CS-08-002 accordingly.

**TECHDEBT-28** — Added `_idempotent_create(dl, type_key, id_key, obj, label,
activity_id) -> bool` helper to `_helpers.py`. Replaced the repeated
idempotency-guard-then-create pattern in 10 use-case `execute()` methods
(`CreateEmbargoEvent`, `CreateNote`, `CreateCaseParticipant`, `CreateCaseStatus`,
`CreateParticipantStatus`, `SuggestActorToCase`, `AcceptSuggestActorToCase`,
`OfferCaseOwnershipTransfer`, `InviteActorToCase`, `InviteToEmbargoOnCase`).

**Test results:** 893 passed, 0 failed (unchanged from baseline).

---

## TECHDEBT-27 — Standardize error handling in use cases (2026-03-17)

Removed all silent `except Exception as e: logger.error(...)` swallowers
(with no re-raise) from every `execute()` method in 7 use case files:
`actor.py`, `case.py`, `case_participant.py`, `embargo.py`, `note.py`,
`report.py`, `status.py`. Domain exceptions now propagate naturally out of
use cases.

Added catch-log-reraise in `DispatcherBase._handle()`: unexpected exceptions
are logged at ERROR level with `exc_info=True` (full stack trace) and then
re-raised, satisfying the dispatcher-boundary requirement.

Inner `try/except ValueError` idempotency guards in `report.py` and `case.py`
(`CloseCaseReceivedUseCase`) were preserved unchanged.

**Test results:** 913 passed, 0 failed.

---

## P75-5 — Remove api/v1 and consolidate vocabulary examples into api/v2 (2026-03-17)

Decided to remove `vultron/api/v1/` entirely (Option B from ADR-0011).
The v1 package was ~1 100 lines of stub endpoints that returned `vocab_examples`
objects with no business logic. All protocol work lives in v2.

Changes:

- Created `docs/adr/0011-remove-api-v1.md` recording the decision.
- Expanded `vultron/api/v2/routers/examples.py` to include vocabulary-showcase
  endpoints for `reports`, `cases`, `cases/statuses`, `cases/participants`,
  `cases/participants/statuses`, and `cases/embargoes` (migrated from
  `vultron/api/v1/routers/examples.py`).
- Updated the v2 app's `Examples` tag description.
- Removed `from vultron.api.v1 import app_v1` and `/api/v1` mount from
  `vultron/api/main.py`. Updated landing page to link only to v2 docs.
- Deleted `vultron/api/v1/` directory (all 7 files).

**Test results:** 913 passed, 0 failed (no regressions).

---

## TECHDEBT-16 — DRY core domain models: VultronObject base class (2026-03-18)

Added `VultronObject` base class to `vultron/core/models/base.py`. This class
captures the three fields shared by all domain object models: `as_id` (with
`_new_urn` factory default), `as_type` (required; subclasses provide defaults),
and `name` (`str | None = None`). Mirrors the `as_Base`/`as_Object` hierarchy
in the wire layer.

All 12 concrete domain object classes now inherit from `VultronObject`:
`VultronReport`, `VultronCase`, `VultronNote`, `VultronParticipant`,
`VultronParticipantStatus`, `VultronCaseStatus`, `VultronEmbargoEvent`,
`VultronCaseActor`, `VultronActivity`, `VultronOffer`, `VultronAccept`,
`VultronCreateCaseActivity`.

Repeated `as_id` and `name` field definitions removed from all 12 classes.
`as_type` remains in each subclass with its specific default (or required in
`VultronActivity`). Unused `BaseModel`, `Field`, and `_new_urn` imports cleaned
up from affected modules.

`VultronEvent` (events/base.py) was intentionally excluded — it represents an
inbound domain message envelope with different semantics (`activity_id`,
`semantic_type`) rather than a persistent domain object.

`vultron/core/models/__init__.py` updated to export `VultronObject`.

New tests added in `test/core/models/test_base.py` verifying inheritance,
`as_id` generation, `as_type` defaults, and `name` field presence for all
12 domain object classes.

**Test results:** 961 passed (+48), 5581 subtests, 0 failed.

---

## VCR-A — Batch VCR-A dead code and shim removal (2026-03-18)

**Tasks completed**: VCR-001, VCR-015a, VCR-015b, VCR-024, VCR-031, VCR-032
**Tasks skipped**: VCR-006 (depends on PREPX-2), VCR-030 (blocked — see below)

### What was done

- **VCR-001**: Deleted `vultron/adapters/driven/dns_resolver.py` (stub with no
  implementation or callers). Updated `vultron/adapters/driven/__init__.py` docstring.
- **VCR-015a**: Deleted `vultron/api/v2/data/status.py` (shim re-exporting from
  `vultron.core.models.status`). Updated 4 callers to import from the canonical
  source: `test/core/behaviors/report/test_validate_tree.py`,
  `test/core/behaviors/report/test_nodes.py`,
  `test/api/v2/routers/test_trigger_report.py`,
  `test/api/v2/backend/test_trigger_services.py`.
- **VCR-015b**: Deleted `vultron/api/v2/data/types.py` (`UniqueKeyDict` class with
  no callers outside its own file).
- **VCR-024**: Deleted `vultron/core/ports/dns_resolver.py` (Protocol stub with no
  callers).
- **VCR-031**: Deleted `vultron/behavior_dispatcher.py` (backward-compat shim).
  Updated `test/test_behavior_dispatcher.py` to import `get_dispatcher` and
  `DirectActivityDispatcher` directly from `vultron.core.dispatcher`.
- **VCR-032**: Moved `VultronApiHandlerNotFoundError` from
  `vultron/dispatcher_errors.py` into `vultron/errors.py`. Updated
  `vultron/core/dispatcher.py` and `vultron/api/v2/errors.py` to import from
  `vultron.errors`. Deleted `vultron/dispatcher_errors.py`.

### VCR-030 blocked

VCR-030 (delete `vultron/sim/`) was found to have callers in `vultron/bt/`:

- `vultron/bt/states.py`
- `vultron/bt/messaging/outbound/behaviors.py`
- `vultron/bt/messaging/inbound/fuzzer.py`
- `vultron/bt/report_management/_behaviors/report_to_others.py`

All import `vultron.sim.messages.Message`. VCR-030 is updated in the plan to
reflect the blocked status and the prerequisite work needed.

### Test results

966 passed, 5581 subtests, 5 warnings (up from 961 before this batch).

---

## PREPX-1 — Fix BT status string comparisons (2026-03-18)

Replaced three `result.status.name != "SUCCESS"` string comparisons with
`result.status != Status.SUCCESS` enum comparisons in
`vultron/core/use_cases/case.py` (`CreateCaseReceivedUseCase`,
`EngageCaseReceivedUseCase`, `DeferCaseReceivedUseCase`).
Added `from py_trees.common import Status` import. No logic change.

### Test results

966 passed, 5581 subtests, 5 warnings (unchanged).

---

## PREPX-2 — Remove handlers shim layer (2026-03-18)

Deleted the backward-compatibility shim layer:

- `vultron/api/v2/backend/handlers/__init__.py` (re-exported all 38 use cases
  as thin wrapper functions with `_unwrap` helper)
- `vultron/api/v2/backend/handlers/_shim.py` (no-op `verify_semantics` decorator)

Updated two test files to call use-case classes directly with `VultronEvent`
objects instead of going through the shim:

- `test/api/v2/backend/test_handlers.py`: removed `DispatchEvent` usage,
  `_make_dispatchable()` helper, and obsolete shim test classes
  (`TestVerifySemanticsDecorator`, `TestHandlerDecoratorPresence`); updated all
  `handlers.foo(dispatchable, dl)` calls to `FooReceivedUseCase(dl, event).execute()`.
- `test/api/test_reporting_workflow.py`: replaced handler-based `_call_handler`
  helper with `_call_use_case`; moved `TinyDbDataLayer` import into the `dl`
  fixture to avoid a circular-import startup issue.

VCR-006 (delete `handler_map.py` shim) is now unblocked.
PREPX-3 (remove `DispatchEvent` and `InboundPayload` aliases) is now unblocked.

### Test results

961 passed, 5581 subtests, 5 warnings (5 fewer due to removed shim-specific tests).

---

## VCR-006 — Delete `handler_map.py` shim (2026-03-18)

**Task**: Delete `vultron/api/v2/backend/handler_map.py`, the backward-compat
shim that re-exported `USE_CASE_MAP` as `SEMANTICS_HANDLERS`.

**What was done**:

- Updated `test/test_semantic_handler_map.py` to import `USE_CASE_MAP` directly
  from `vultron.core.use_cases.use_case_map` and use it in place of
  `SEMANTICS_HANDLERS`.
- Deleted `vultron/api/v2/backend/handler_map.py`.

### Test results

981 passed, 5581 subtests, 5 warnings.

---

## PREPX-3 — Remove `DispatchEvent` and `InboundPayload` deprecated aliases (2026-03-18)

**Task**: Remove the `DispatchEvent` backward-compat wrapper from
`vultron/types.py` and the `InboundPayload` alias from
`vultron/core/models/events/__init__.py`. Neither was referenced outside its
definition file after PREPX-2 removed the handler shim layer.

**What was done**:

- Deleted `DispatchEvent` class and `DispatchActivity = DispatchEvent` alias
  from `vultron/types.py`. Removed the now-unused `BaseModel` and
  `MessageSemantics` imports. `BehaviorHandler` Protocol retained.
- Removed `InboundPayload = VultronEvent` alias and its `__all__` entry from
  `vultron/core/models/events/__init__.py`. Updated module docstring.
- Updated `specs/handler-protocol.md`: HP-01-001 now reflects the use-case
  class interface; HP-02-001 implementation note updated; verification
  criteria updated.
- Updated `specs/dispatch-routing.md`: Overview and DR-01-002 reflect
  `VultronEvent` + `DataLayer`; DR-02 verification uses `USE_CASE_MAP`;
  Related section updated to canonical paths.
- Updated `specs/code-style.md`: docstring example uses a use-case class.
- Updated `AGENTS.md`: quickstart example, Use-Case Protocol section,
  Registry Pattern section, Decorator Usage section, Quick Reference
  "Adding a New Message Type", Handler Testing checklist, Key Files Map
  (removed deleted shim entries), and Test Data Quality anti-pattern.

### Test results

981 passed, 5581 subtests, 5 warnings.

---

## VCR-028 — Remove unnecessary `_idempotent_create` guard patterns (2026-03-18)

**Task**: Remove `if _idempotent_create(...): return` guard patterns in use
cases where the guard is the complete `execute()` body.

### What was done

- Changed `_idempotent_create` return type from `-> bool` to `-> None` in
  `vultron/core/use_cases/_helpers.py`. The return value was only ever used
  as a guard (`if ...: return`) and never inspected further.
- Replaced all 10 `if _idempotent_create(...): return` guards with direct
  calls to `_idempotent_create(...)` in:
  - `actor.py` (4 sites: `SuggestActorToCase`, `AcceptSuggestActorToCase`,
    `OfferCaseOwnershipTransfer`, `InviteActorToCase`)
  - `case_participant.py` (1 site: `CreateCaseParticipant`)
  - `embargo.py` (2 sites: `CreateEmbargoEvent`, `InviteToEmbargoOnCase`)
  - `note.py` (1 site: `CreateNote`)
  - `status.py` (2 sites: `CreateCaseStatus`, `CreateParticipantStatus`)

No behaviour change. The `_idempotent_create` helper already handles all
logic internally (existence check, creation, logging). The `if ...: return`
was redundant because there was no code after the guard in any of these
`execute()` methods.

### Test results

981 passed, 5581 subtests, 5 warnings.

---

## VCR-016 — Move adapter-layer utils to `vultron/adapters/utils.py` (2026-03-18)

**Task**: Evaluate `vultron/api/v2/data/utils.py` and move to the correct
architectural location.

**Finding**: All callers of `utils.py` are in the adapter or demo layer —
no core module imports from it.  The file provides HTTP URL and URN ID
utilities (`make_id`, `id_prefix`, `parse_id`, `strip_id_prefix`,
`_URN_UUID_PREFIX`, `_UUID_RE`) that are specific to the wire-format ID
conventions used by the TinyDB adapter and demo scripts.  Core has no
duplicative needs.  Conclusion: adapter-only utilities.

**What was done**:

- Moved `vultron/api/v2/data/utils.py` → `vultron/adapters/utils.py`.
  Updated the module docstring to explain the adapter-layer placement.
- Updated all callers to import from `vultron.adapters.utils`:
  `vultron/adapters/driven/datalayer_tinydb.py`,
  `vultron/api/v2/data/actor_io.py`,
  `vultron/demo/utils.py`,
  `vultron/demo/acknowledge_demo.py`,
  `vultron/demo/receive_report_demo.py`.
- Moved test: `test/api/v2/data/test_utils.py` → `test/adapters/test_utils.py`
  (mirrors new source location). Created `test/adapters/__init__.py` and
  `test/adapters/conftest.py` with the `test_base_url` fixture.
- Removed the now-unnecessary `test_base_url` fixture and `utils` import
  from `test/api/v2/data/conftest.py`.
- Updated `test/api/v2/data/test_actor_io.py` to import `parse_id` from the
  new location.

### Test results

981 passed, 5581 subtests, 5 warnings.

---

## VCR-B — Move FastAPI adapter to vultron/adapters/driving/fastapi/ (2026-03-18)

**Task**: VCR-003/004/007/008/009/017/018 (Batch VCR-B)

### What was done

Created `vultron/adapters/driving/fastapi/` subpackage consolidating all
FastAPI-specific code from the former `vultron/api/v2/` location:

- `vultron/api/v2/routers/` → `vultron/adapters/driving/fastapi/routers/`
- `vultron/api/v2/app.py` → `vultron/adapters/driving/fastapi/app.py`
- `vultron/api/main.py` → `vultron/adapters/driving/fastapi/main.py`
- `vultron/api/v2/backend/inbox_handler.py` → `vultron/adapters/driving/fastapi/inbox_handler.py`
  (replaced the stub at `vultron/adapters/driving/http_inbox.py`)
- `vultron/api/v2/backend/outbox_handler.py` → `vultron/adapters/driving/fastapi/outbox_handler.py`
- `vultron/api/v2/errors.py` → `vultron/adapters/driving/fastapi/errors.py`
- `vultron/api/v2/backend/helpers.py` → `vultron/adapters/driving/fastapi/helpers.py`

External callers updated: `vultron/adapters/driving/cli.py`, `docker/Dockerfile`,
9 test files. No backward-compat shims left behind.

Remaining in `vultron/api/`: `actor_io.py` (VCR-014), `trigger_services/` (VCR-D),
`datalayer/` stub package. These are handled by separate tasks.

### Test results

981 passed, 5581 subtests, 5 warnings.

---

## VCR-019c — Enum/state consolidation study (2026-03-18)

**Task**: Study task — identify which enums across `vultron/case_states/` and
`vultron/bt/**/states.py` can be consolidated before implementing VCR-019a/b.

**What was done**: Inventoried all state/enum definitions across both packages
and analysed cross-layer import patterns to determine correct relocation targets
for VCR-019a/b. Documented findings in `plan/IMPLEMENTATION_NOTES.md`.

**Key findings**:

- No duplicates exist between `case_states/` enums and `bt/**/states.py` enums.
- Enums categorised into four groups:
  - **Group A** (move to `vultron/core/states/`): `RM`, `EM`, `CS`/`CS_vfd`/
    `CS_pxa`/component IntEnums/helper functions, `CVDRoles`
  - **Group B** (merge into `vultron/errors.py`): `CvdStateModelError`
    hierarchy
  - **Group C** (move with `case_states/` as `vultron/core/case_states/`):
    `EmbargoViability`, SSVC-2, CVSS-3.1, `Actions`, VEP, zero-day enums
  - **Group D** (stay in `vultron/bt/`): `MessageTypes`, `CapabilityFlag`,
    `ActorState`
- VCR-019a/b plan updated with prerequisite notes and clarified scope (019b
  scope narrowed: only Group A enums move; `ActorState` stays in bt/).
- 60+ import sites in `vultron/` and 21+ in `test/` will need updating in
  VCR-019a/b.

**Lessons learned**: The plan listed 019c after 019a/b; in practice it is a
prerequisite. Updated plan task ordering to reflect this dependency.

### Test results

No code changes; test suite unchanged at 981 passed, 5581 subtests.

---

## VCR-019a — Move case_states/ into vultron/core/ (2026-03-19)

### What was done

Relocated `vultron/case_states/` into `vultron/core/` with no compatibility shims.

**New packages created:**

- `vultron/core/states/` — CS enum and related state machine definitions
  (`CS`, `CS_vfd`, `CS_pxa`, `VendorAwareness`, `FixReadiness`, `FixDeployment`,
  `PublicAwareness`, `ExploitPublication`, `AttackObservation`, `CompoundState`,
  `VfdState`, `PxaState`, `State`, helper functions `state_string_to_enums`,
  `state_string_to_enum2`, `all_states`). `cs.py` is the implementation module;
  `__init__.py` re-exports all public symbols.

- `vultron/core/scoring/` — Assessment/scoring enums moved from
  `vultron/case_states/enums/`: `EmbargoViability`, SSVC-2, CVSS-3.1, VEP,
  `Actions`, zero-day types, and utilities (`unique_enum_list`, `enum2title`,
  `enum_item_in_list`).

- `vultron/core/case_states/` — Remainder of `case_states/`: `validations.py`,
  `type_hints.py`, `hypercube.py`, `make_doc.py`, and `patterns/` subpackage.

**Errors merged:**

- `CvdStateModelError` hierarchy from `vultron/case_states/errors.py` appended
  directly to `vultron/errors.py`; all classes now inherit from `VultronError`.

**Callers updated:** 12 files in `vultron/`, 21 files in `test/`.

**Test directory renamed:** `test/case_states/` → `test/core/case_states/`.

**Deleted:** `vultron/case_states/` entirely.

### Test results

981 passed, 5581 subtests (unchanged from baseline).

---

## DOCS-2 — Fix broken inline code examples in `docs/` (2026-03-18)

Updated `docs/reference/code/as_vocab/*.md` to replace all `vultron.as_vocab.*`
autodoc directives with the correct `vultron.wire.as2.vocab.*` paths that were
introduced in P60-1. Affected files: `index.md`, `as_base.md`, `as_activities.md`,
`as_links.md`, `as_objects.md`, `v_activities.md`, `v_objects.md`.

`mkdocs build` succeeds with no module-not-found errors in
`docs/reference/code/as_vocab/`.

### Test results

982 passed, 5581 subtests (unchanged from baseline).

---

## VCR-030 — Delete `vultron/sim/`, relocate `Message` (2026-03-18)

`vultron/sim/` contained only `__init__.py` and `messages.py`. The `Message`
class in `messages.py` was the sole dependency, imported by 4 files in
`vultron/bt/`:

- `vultron/bt/states.py`
- `vultron/bt/messaging/outbound/behaviors.py`
- `vultron/bt/messaging/inbound/fuzzer.py`
- `vultron/bt/report_management/_behaviors/report_to_others.py`

`Message` was moved to `vultron/bt/messaging/message.py` (new module), which is
a more appropriate location since it is only used by the bt simulator. All 4
callers updated to import from the new location. `vultron/sim/` deleted.

### Test results

982 passed, 5581 subtests (unchanged from baseline).

---

## VCR-019b — Move RM, EM, CVDRoles enums to `vultron/core/states/` (2026-03-19)

Moved three enum modules from `vultron/bt/` subpackages into
`vultron/core/states/`:

- `vultron/bt/report_management/states.py` → `vultron/core/states/rm.py`
  (exports `RM`, `RM_CLOSABLE`, `RM_UNCLOSED`, `RM_ACTIVE`)
- `vultron/bt/embargo_management/states.py` → `vultron/core/states/em.py`
  (exports `EM`)
- `vultron/bt/roles/states.py` → `vultron/core/states/roles.py`
  (exports `CVDRoles`, `add_role`)

Updated `vultron/core/states/__init__.py` to re-export all new symbols
alongside the existing CS exports. Updated all 59 callers across `vultron/`,
`test/`, and `integration_tests/` with `sed` bulk replacement. Deleted the
original source files with no shims.

`MessageTypes`, `CapabilityFlag`, and `ActorState` remain in `vultron/bt/`
per the VCR-019c study (Group D — BT-runtime-only, no callers in core).

### Test results

982 passed, 5581 subtests (unchanged from baseline).

---

## VCR-023 — Delete `delivery_queue.py` stubs, update architecture notes (2026-03-19)

Confirmed no callers of `DeliveryQueue` or `delivery_queue` anywhere in
production code or tests, then deleted:

- `vultron/core/ports/delivery_queue.py` (Protocol stub)
- `vultron/adapters/driven/delivery_queue.py` (empty stub)

Updated `notes/architecture-ports-and-adapters.md`:

- Removed `delivery_queue.py` and `dns_resolver.py` (already deleted in
  VCR-024/VCR-001) from both the `ports/` and `adapters/driven/` tree listings
- Replaced the `DeliveryQueue`-based code example with a `DataLayer`-based
  example reflecting actual current use-case patterns
- Reorganized the ports section: moved removed ports to a "Ports that have
  been removed" subsection; moved `dispatcher.py` to "Ports to evaluate
  for removal" (VCR-025)

Updated `vultron/adapters/driven/__init__.py` to remove the `delivery_queue.py`
reference from the module docstring.

The `ActivityEmitter` port will be created in OX-1.0 as the correct
successor to `DeliveryQueue`.

### Test results

982 passed, 5581 subtests (unchanged from baseline).

---

## VCR-010 — Rename trigger service functions to `_trigger` suffix

**Date**: 2026-03-19
**Phase**: PRIORITY-80 / VCR-D

Renamed all 9 trigger service functions in
`vultron/api/v2/backend/trigger_services/` from the `svc_` prefix to the
`_trigger` suffix, per `specs/code-style.md` CS-12-002 (the `Svc` prefix is
reserved for use-case class names only):

- `svc_engage_case` → `engage_case_trigger`
- `svc_defer_case` → `defer_case_trigger`
- `svc_propose_embargo` → `propose_embargo_trigger`
- `svc_evaluate_embargo` → `evaluate_embargo_trigger`
- `svc_terminate_embargo` → `terminate_embargo_trigger`
- `svc_validate_report` → `validate_report_trigger`
- `svc_invalidate_report` → `invalidate_report_trigger`
- `svc_reject_report` → `reject_report_trigger`
- `svc_close_report` → `close_report_trigger`

Updated callers in:

- `vultron/adapters/driving/fastapi/routers/trigger_case.py`
- `vultron/adapters/driving/fastapi/routers/trigger_embargo.py`
- `vultron/adapters/driving/fastapi/routers/trigger_report.py`

Updated test imports and test names in:

- `test/api/v2/backend/test_trigger_services.py`

Pure mechanical rename, no behaviour change. 982 tests pass.

---

### VCR-025 + VCR-026 — Port Taxonomy Labels (2026-03-19)

**Task**: VCR-025: Evaluate ActivityDispatcher Protocol. VCR-026: Label all
port files in `core/ports/` as inbound (driving) or outbound (driven) per
`specs/architecture.md` ARCH-11-001.

**VCR-025 evaluation result**: `ActivityDispatcher` in
`vultron/core/ports/dispatcher.py` is still needed and retained. It is
actively used in `vultron/core/dispatcher.py` (return type of
`get_dispatcher()`) and `vultron/adapters/driving/fastapi/inbox_handler.py`
(module-level type annotation). Its `dispatch(event, dl)` contract is
distinct from `UseCase[Req, Res].execute()`: the dispatcher routes an event
to a use case; the use case executes a single operation. They serve different
levels of the dispatch pipeline and cannot be collapsed.

**VCR-026 changes**:

- `vultron/core/ports/dispatcher.py`: updated module docstring to say
  "Inbound (driving) port" with description of port direction.
- `vultron/core/ports/use_case.py`: updated module docstring to say
  "Inbound (driving) port" with description of port direction.
- `vultron/core/ports/datalayer.py`: updated module docstring to say
  "Outbound (driven) port" with description of port direction.
- `vultron/core/ports/__init__.py`: updated package docstring to list
  the full inbound/outbound port taxonomy with file references.

No ports removed (VCR-023 and VCR-024 already handled prior removals;
VCR-025 confirmed ActivityDispatcher is retained). 982 tests pass.

## VCR-019e — Convert non-StrEnum Enums to StrEnum (2026-03-19)

**Task**: Convert older non-StrEnum Enums to `StrEnum` where semantically
appropriate, per VCR-019c study results.

**What was done**:

1. Converted 6 `IntEnum` component classes in `vultron/core/states/cs.py`
   to `StrEnum`:
   - `VendorAwareness`: values "v" / "V"
   - `FixReadiness`: values "f" / "F"
   - `FixDeployment`: values "d" / "D"
   - `PublicAwareness`: values "p" / "P"
   - `ExploitPublication`: values "x" / "X"
   - `AttackObservation`: values "a" / "A"
   The lowercase/uppercase letters directly correspond to the state-string
   notation already used throughout the codebase (e.g., "vfdpxa").
   Updated `state_string_to_enum2` return type annotation from
   `Tuple[IntEnum, ...]` to `Tuple[StrEnum, ...]`.

2. Converted `MessageTypes` in `vultron/bt/messaging/states.py` from
   plain `Enum` to `StrEnum`. Removed the `VULTRON_MESSAGE_EMBARGO_REVISION_*`
   primary entries (these were already Python aliases for the non-REVISION
   variants since they shared the same string values). The short aliases
   `EV`, `EJ`, `EC` are retained as explicit aliases for `EP`, `ER`, `EA`
   respectively to avoid breaking callsites. Removed the `EmbargoRevisionProposal`,
   `EmbargoRevisionRejected`, `EmbargoRevisionAccepted` long-name aliases.
   Removed the `__str__` override (StrEnum provides str() = value by default).
   Cleaned up `EM_MESSAGE_TYPES` to remove the duplicate EV/EJ/EC entries.

3. Updated `test/bt/test_case_states/test_states.py`:
   `test_state_string_to_enum2` now checks string values (`str(result[i]) == c`)
   instead of integer values (`== 0` / `== 1`).

4. Updated `test/bt/test_behaviortree/test_messaging/test_messaging_states.py`:
   Replaced assertions that EV/EJ/EC are aliases for the now-removed
   `EmbargoRevisionProposal/Rejected/Accepted` with assertions that EV/EJ/EC
   are aliases for EP/ER/EA.

**Result**: 982 tests pass. The string values of `VendorAwareness`, etc. now
match the state-string notation directly, making the codebase more self-
documenting and removing the historical IntEnum artifact.

---

## VCR-020/021a/021b/022/029 — VultronEvent activity field and docstring cleanup (2026-03-19)

**Tasks completed**: VCR-020, VCR-021a, VCR-021b, VCR-022, VCR-029

### What was done

**VCR-020**: Added `activity: VultronActivity | None = None` to `VultronEvent`
in `vultron/core/models/events/base.py`. This satisfies ARCH-10-001 (fail-fast
domain objects): the base class permits `None` for semantics that don't use the
full activity object; the 12 concrete subclasses that always carry an activity
already narrowed the field to required by declaring `activity: VultronActivity`
without a default. The base class now imports `VultronActivity` from
`vultron.core.models.activity` (no circular imports).

**VCR-021a**: Clarified the distinction between `VultronActivity` and
`VultronEvent` in their docstrings. `VultronActivity` is the domain model for
AS2 activity objects stored in the DataLayer; `VultronEvent` is the semantic
dispatch event carrying decomposed ID/type fields used for handler routing.
A `VultronEvent` may carry a `VultronActivity` as its `activity` field, but
the two types serve different purposes.

**VCR-021b / VCR-029**: Verified all concrete domain object fields in event
subclasses (`report`, `case`, `embargo`, `participant`, `note`, `status`,
`activity`) are already non-optional where the value is always present. No
code changes required for these two tasks.

**VCR-022**: Verified as equivalent to TECHDEBT-16 (already complete).
`VultronObject` base class exists in `vultron/core/models/base.py` and all
10 domain object model classes inherit from it.

**Result**: 982 tests pass, 5 warnings unchanged.

---

## VCR-027 — Move Protocol types to core/models/protocols.py (2026-03-19)

**Task**: Evaluate whether `CaseModel` and `ParticipantModel` Protocol types in
`vultron/core/use_cases/_types.py` belong in `vultron/core/models/`.

**Decision**: Yes — these protocols define the structural interface of domain
model objects (VultronCase, VultronParticipant) and belong alongside the
concrete domain models in `vultron/core/models/`.

**What was done**:

- Created `vultron/core/models/protocols.py` with `CaseModel` and
  `ParticipantModel` Protocol definitions (moved verbatim from `_types.py`).
- Updated 7 callers to import from `vultron.core.models.protocols`:
  `triggers/_helpers.py`, `case_participant.py`, `embargo.py`, `case.py`,
  `actor.py`, `note.py`, `status.py`.
- Deleted `vultron/core/use_cases/_types.py`.

**Result**: 982 tests pass, 5 warnings unchanged.

---

## VCR-011 — Abstract trigger service error-handling pattern (2026-03-19)

**Task**: Abstract the repeated `try: ... except (VultronError, PydanticValidationError)
as e: raise translate_domain_errors(e)` block in trigger service adapter modules
into a shared `domain_error_translation()` context manager.

**What was done**:

- Added `domain_error_translation()` `@contextmanager` to
  `vultron/api/v2/backend/trigger_services/_helpers.py`. It catches both
  `VultronError` and `PydanticValidationError` and raises the result of
  `translate_domain_errors(e)`.
- Added `VultronError` to the `vultron.errors` import in `_helpers.py`
  (previously only subclasses were imported).
- Replaced the `try/except` boilerplate in all 9 trigger functions across
  `embargo.py` (3 functions), `report.py` (4 functions), and `case.py`
  (2 functions) with `with domain_error_translation():`.
- Removed now-redundant direct imports of `translate_domain_errors`,
  `VultronError`, and `PydanticValidationError` from the three callers.
- Fixed a pre-existing inconsistency: `report.py` only caught `VultronError`
  (not `PydanticValidationError`). The context manager now handles both
  consistently across all three files.

**Result**: 982 tests pass, 5 warnings unchanged.

---

## VCR-012 — Remove duplicated URI validation from `_models.py`

**Date**: 2026-03-19

**What was done**:

- Reviewed `vultron/api/v2/backend/trigger_services/_models.py` per VCR-012.
- Confirmed the core domain trigger request models already live in
  `vultron/core/use_cases/triggers/requests.py` (completed as TECHDEBT-23).
  `_models.py` is correctly the HTTP adapter layer (no `actor_id`; used as
  FastAPI request body schemas).
- Identified the real duplication: the `_URI_SCHEME_RE` pattern and
  `case_id_must_be_uri` validator were duplicated in both `_models.py` and
  `requests.py`.
- Extracted `UriString = Annotated[NonEmptyString, AfterValidator(_valid_uri)]`
  into `vultron/core/models/base.py` alongside `NonEmptyString`. This is the
  canonical type alias for a validated URI string.
- Updated `requests.py` to import `UriString` from `base.py`; removed its own
  `_URI_SCHEME_RE`, `_valid_uri`, `CaseIdString`, and `import re`.
- Updated `_models.py` to import `UriString` and `NonEmptyString` from core;
  removed 4 duplicated `case_id_must_be_uri` validators and `_URI_SCHEME_RE`.
  Tightened `offer_id` and `note` fields to `NonEmptyString`.
- Updated `_models.py` docstring to clarify it is the HTTP adapter layer.

**Result**: 982 tests pass.

---

## DOCS-1 — Update `docker/README.md` (2026-03-19)

**Task**: Update `docker/README.md` to accurately reflect the current
docker-compose services.

**What was done**:

- Replaced the outdated list of individual per-demo service entries
  (`receive-report-demo`, `initialize-case-demo`, `establish-embargo-demo`,
  `invite-actor-demo`, `status-updates-demo`, `suggest-actor-demo`,
  `transfer-ownership-demo`) with the consolidated `demo` service.
- Updated the "Running Demos" section to document the `DEMO` env-var
  non-interactive mode and the interactive shell mode.
- Listed all available `vultron-demo` sub-commands.
- Retained the Networking and Customizing sections unchanged.
- Linted with `markdownlint-cli2`: 0 errors.

**Result**: `docker/README.md` now accurately reflects the five services
(`api-dev`, `demo`, `test`, `docs`, `vultrabot-demo`) in the current
`docker-compose.yml`.

---

## VCR-005 — Actor Profile Discovery Endpoint (2026-03-19)

**Task**: Add `GET /actors/{actor_id}/profile` endpoint for actor discovery.

**What was done**:

- Added `GET /actors/{actor_id}/profile` route to
  `vultron/adapters/driving/fastapi/routers/actors.py`. Returns the actor's
  `as_Actor` object (with `inbox`, `outbox`, `name`, `type`, and all other
  profile fields) serialized as ActivityStreams JSON.
- The endpoint reuses the same actor lookup pattern as `GET /actors/{actor_id}`
  (full URI lookup, fallback to `find_actor_by_short_id`, HTTP 404 if absent).
  No new model or DataLayer changes were needed.
- Added two new tests to `test/api/v2/routers/test_actors.py`:
  `test_get_actor_profile_returns_discovery_fields` and
  `test_get_actor_profile_not_found_returns_404`.
- Added requirements `AR-10-001` through `AR-10-003` and verification criteria
  to `specs/agentic-readiness.md`.

**Result**: 984 tests pass (2 new tests added).

---

## OX-1.0 — ActivityEmitter port stub (2026-03-19)

**Task**: Add `vultron/core/ports/emitter.py` — `ActivityEmitter` Protocol
(outbound counterpart to `core/ports/dispatcher.py`).

**What was done**:

- Created `vultron/core/ports/emitter.py` with the `ActivityEmitter` Protocol.
  Defines `emit(activity: VultronActivity, recipients: list[str]) -> None` as
  the outbound (driven) port contract for delivering activities to recipient
  actor inboxes.
- Created `vultron/adapters/driven/delivery_queue.py` with a stub
  `DeliveryQueueAdapter` class that imports and implements `ActivityEmitter`.
  The stub logs a debug message and returns; the body will be filled in OX-1.1.
- Updated `vultron/core/ports/__init__.py` and
  `vultron/adapters/driven/__init__.py` docstrings to reflect the new modules.

**Result**: 984 tests pass (no regressions). OX-1.1 (local delivery
implementation) is now unblocked.

## ACT-1 — ADR for per-actor DataLayer isolation (2026-03-19)

**Task**: Draft ADR-0012 for per-actor DataLayer isolation, resolving four
design decisions required before ACT-2 implementation can begin.

**What was done**:

- Created `docs/adr/0012-per-actor-datalayer-isolation.md` (status: accepted).
- Added ADR-0011 and ADR-0012 entries to `docs/adr/index.md` (ADR-0011 was
  previously missing from the index).
- Marked ACT-1 complete in `plan/IMPLEMENTATION_PLAN.md`.

**Decisions recorded**:

1. **DataLayer isolation strategy**: Option B — TinyDB namespace prefix (one
   table per `actor_id`) as the near-term prototype implementation, with
   MongoDB Community Edition as the concurrent production-grade target.
2. **`get_datalayer` FastAPI DI strategy**: Closure lambda —
   `Depends(lambda actor_id=Path(...): get_datalayer(actor_id))` — applied
   uniformly across all route files in ACT-3.
3. **`actor_io.py` inbox/outbox ownership**: Migrate inbox/outbox into the
   per-actor DataLayer as TinyDB collections (`{actor_id}_inbox`,
   `{actor_id}_outbox`); remove `actor_io.py` after ACT-2 (unblocks VCR-014).
4. **OUTBOX-1 scope boundary**: Defer OX-1.1–OX-1.4 until ACT-3 is complete
   to avoid implementing delivery against a still-changing DataLayer.

**Result**: 984 tests pass (no regressions; docs-only change).

---

### TECHDEBT-31 — Relocate `trigger_services/` into FastAPI adapter (2026-03-23)

**Task**: Move `vultron/api/v2/backend/trigger_services/` into the proper
FastAPI adapter layer under `vultron/adapters/driving/fastapi/`.

**What was done**:

- Moved `domain_error_translation()` and `translate_domain_errors()` from
  `trigger_services/_helpers.py` into
  `vultron/adapters/driving/fastapi/errors.py`.
- Moved HTTP request body models from `trigger_services/_models.py` to
  `vultron/adapters/driving/fastapi/trigger_models.py` (unchanged content).
- Merged all three thin adapter delegate modules (`case.py`, `embargo.py`,
  `report.py`) into a single
  `vultron/adapters/driving/fastapi/_trigger_adapter.py`.
- Updated all three trigger routers (`trigger_report.py`, `trigger_case.py`,
  `trigger_embargo.py`) to import from the new adapter-layer locations.
- Updated `test/api/v2/backend/test_trigger_services.py` imports.
- Deleted `vultron/api/v2/backend/trigger_services/` entirely (5 Python files).
- `vultron/api/v2/` now contains only `data/actor_io.py` (pending VCR-014)
  and two `__init__.py` stubs.

**Result**: 996 tests pass, no regressions.

**Notes**: The old `_helpers.py` re-export shim (which re-exported core helpers
like `add_activity_to_outbox`, `resolve_actor` etc.) is now gone entirely.
All callers already imported those from `vultron.core.use_cases.triggers._helpers`
directly (confirmed by test suite passing).

---

### TECHDEBT-29 — Profile endpoint returns inbox/outbox as URL strings (2026-03-23)

**Task**: Clarify and enforce that `GET /actors/{actor_id}/profile` returns
inbox and outbox as URL strings, not embedded OrderedCollection objects.

**What was done**:

- Updated `specs/agentic-readiness.md` AR-10-001 to require `inbox` and
  `outbox` as string URL links (not embedded collection objects); updated
  the verification section accordingly.
- Modified `vultron/adapters/driving/fastapi/routers/actors.py`
  `get_actor_profile()`: removed `response_model=as_Actor`; profile is now
  built via `model_dump(by_alias=True, exclude_none=True)` then inbox/outbox
  overridden with their `.as_id` string URLs.
- Updated `test/api/v2/routers/test_actors.py` to assert `inbox` and `outbox`
  are `str` instances (not dicts).

**Result**: 996 tests pass, no regressions. Spec and test now agree.

**Notes**: The existing `as_Actor.inbox` default_factory creates collections
with random UUIDs as IDs (the `set_collections` validator only fires when
`inbox is None`). Fixing the collection IDs to be `{actor_id}/inbox`-style
URLs is a separate concern tracked as a future improvement.

---

## TECHDEBT-33 — Split test_handlers.py (COMPLETE 2026-03-23)

Split the 2227-line monolithic `test/api/v2/backend/test_handlers.py` into
per-module test files under `test/core/use_cases/`, mirroring the source
layout. Four test classes had already been migrated in earlier runs (actor,
case_participant, basic report/use-case execution); this run completed the
remaining migrations:

- `test_embargo_use_cases.py` — `TestEmbargoUseCases` (11 tests)
- `test_note_use_cases.py` — `TestNoteUseCases` (6 tests)
- `test_status_use_cases.py` — `TestStatusUseCases` (7 tests)
- `test_case_use_cases.py` — `TestCaseUseCases` (6 tests)
- `test_report_use_cases.py` — `TestReportReceiptRM` (3 tests, appended)
- Deleted `test/api/v2/backend/test_handlers.py`

976 tests pass at completion (was 913; the increase reflects newly visible
migrated tests that had previously been duplicated in the old file).

### Commits

- 8f34be9: "test: TECHDEBT-33 — split test_handlers.py into per-module use-case test files"

---

## OB-05-002, AR-01-003, P90-5 — Health readiness probe, operation IDs, OPP-06 spec

**Date**: 2026-03-23
**Commit**: 2d4308e

### What was done

Three Quick Win tasks completed in a single run:

**OB-05-002** — Implemented DataLayer connectivity check in
`/health/ready`. The `readiness()` endpoint now injects the DataLayer via
`Depends(get_datalayer)`, probes it with `dl.read("")`, and returns HTTP 503 if
the backend raises. The test file was updated to use the shared `datalayer`
fixture and a new `client_health_failing` fixture; a new test verifies the 503
path.

**AR-01-003** — Added unique, stable `operation_id` values to all 39 FastAPI
route decorators across `actors.py`, `datalayer.py`, `examples.py`,
`health.py`, `trigger_case.py`, `trigger_embargo.py`, `trigger_report.py`, and
`v2_router.py`. Convention: `{resource}_{action}` (e.g. `actors_list`,
`datalayer_get_offer`, `examples_validate_case`).

**P90-5** — Added `BT-12 VFD/PXA State Machine Usage` section with requirement
`BT-12-001` and verification criteria to `specs/behavior-tree-integration.md`.
Captures OPP-06: any future VFD/PXA state transitions MUST use
`create_vfd_machine()` / `create_pxa_machine()` rather than hand-rolled logic.

### Test results

977 passed, 5581 subtests (baseline was 976; +1 new test for OB-05-002 503 path).

---

## Refresh #43 — OX-1.4 (2026-03-23)

**Task**: OX-1.4 — Add `test/api/v2/backend/test_outbox.py`

**What was done**: Created `test/api/v2/backend/test_outbox.py` with 7 unit
tests for the outbox handler module
(`vultron/adapters/driving/fastapi/outbox_handler.py`).

Tests cover:

- `handle_outbox_item` logs the actor ID and item at INFO level.
- `outbox_handler` drains the actor outbox entirely on success (happy path).
- FIFO order preserved across multiple items (OX-01-002).
- Empty outbox processes nothing.
- Retry and abort after > 3 consecutive errors (item returned to outbox).
- Processing continues after a single recoverable error.

All tests monkeypatch `get_datalayer` in the outbox_handler module so tests
are fast and isolated (no real DataLayer). The pattern mirrors
`test_inbox_handler.py`.

**Bug discovered**: `outbox_handler` does not return early when
`dl.read(actor_id)` returns `None`; the subsequent `while actor.outbox.items:`
would raise `AttributeError`. Documented in `plan/BUGS.md` as BUG-001.

### Test results

984 passed, 5581 subtests (+7 new tests for outbox handler).

---

## P90-1 — Persist RM.RECEIVED ParticipantStatus on report receipt (2026-03-23)

### What was done

Implemented ADR-0013 step 1: the explicit `START → RECEIVED` (RECEIVE trigger)
RM transition is now persisted in a `VultronParticipantStatus` record at
report-receipt time.

**Changes:**

- `vultron/core/use_cases/_helpers.py`: Added `_report_phase_status_id(actor_id,
  report_id, rm_state)` helper that uses UUID v5 (name-based) to generate a
  deterministic, idempotent URN for a report-phase participant status record.
- `vultron/core/use_cases/report.py`: Both `CreateReportReceivedUseCase` and
  `SubmitReportReceivedUseCase` now create and persist a
  `VultronParticipantStatus` with `rm_state=RM.RECEIVED`, `context=report_id`,
  and `attributed_to=actor_id` after storing the report. Uses
  `_idempotent_create` to prevent duplicate records on repeated calls.
  The existing `set_status()` call is retained (P90-4 will remove it).
- `test/core/use_cases/test_report_use_cases.py`: 3 new tests verifying
  persistence for Create, Submit variants, and idempotency.

### Lessons learned

- UUID v5 (name-based) is a clean pattern for deriving deterministic DataLayer
  IDs from semantic keys when auto-generated UUIDs would break idempotency.
- The report ID serves as the `context` for pre-case `VultronParticipantStatus`
  records; the case ID takes over as `context` once a case is created.
- `_idempotent_create` with `dl.get(type_key, id_key)` is the standard
  idempotency guard pattern; deterministic IDs are the prerequisite.

### Test results

987 passed, 5581 subtests (+3 new tests for P90-1).

---

## P90-4 — Remove global STATUS dict; route RM state through DataLayer

**Completed**: 2026-03-23

### What was done

Removed the global mutable `STATUS: dict[str, dict]` from
`vultron/core/models/status.py` along with all helpers that depended on it:
`ReportStatus`, `set_status()`, `get_status_layer()`,
`status_to_record_dict()`, and `_current_report_rm_state()`. The
`OfferStatus`, `OfferStatusEnum`, and `ObjectStatus` classes were retained as
valid domain models.

All RM state reads and writes that previously went through the STATUS layer
now use the DataLayer-backed `VultronParticipantStatus` records introduced in
P90-1, looked up via `_report_phase_status_id()` deterministic IDs.

**Source files changed**:

- `vultron/core/models/status.py` — removed STATUS dict and all related
  helpers; kept `OfferStatusEnum`, `ObjectStatus`, `OfferStatus`
- `vultron/core/use_cases/report.py` — removed remaining `set_status()` calls
  (DataLayer path already present from P90-1)
- `vultron/core/use_cases/triggers/report.py` — replaced `set_status()`
  and `get_status_layer()` with DataLayer `VultronParticipantStatus` creation
  and `dl.get("ParticipantStatus", ...)` existence checks
- `vultron/core/behaviors/report/nodes.py` — updated four BT nodes:
  `CheckRMStateValid` and `CheckRMStateReceivedOrInvalid` now query the
  DataLayer for VALID records; `TransitionRMtoValid` and `TransitionRMtoInvalid`
  create `VultronParticipantStatus` records via `_idempotent_create()`

**Test files changed**:

- `test/core/use_cases/test_report_use_cases.py` — removed `TestReportReceiptRM`
  class (tested STATUS layer, now superseded by `TestReportReceiptPersistsParticipantStatus`)
- `test/api/v2/backend/test_trigger_services.py` — updated `received_report`,
  `accepted_report`, `closed_report` fixtures to use DataLayer
- `test/api/v2/routers/test_trigger_report.py` — same fixture pattern
- `test/core/behaviors/report/test_nodes.py` — replaced `set_status()` setup
  with DataLayer `VultronParticipantStatus` creation; replaced `get_status_layer()`
  assertions with `datalayer.get("ParticipantStatus", ...)` checks
- `test/core/behaviors/report/test_validate_tree.py` — same pattern

### Test results

984 passed, 5581 subtests (no new tests; P90-4 updated existing tests).

---

## TECHDEBT-30 — Domain-specific property getters on core event interfaces (COMPLETE 2026-03-23)

**Goal**: Replace AS2-generic field accesses (`object_id`, `target_id`,
`context_id`, `inner_object_id`, etc.) in core use cases with domain-specific
property names (`report_id`, `case_id`, `embargo_id`, `offer_id`, etc.).

**Approach**: Created `vultron/core/models/events/_mixins.py` with 14 reusable
property-mixin classes. Each mixin exposes one domain-specific property aliasing
the appropriate generic base-class field. Per-semantic event subclasses inherit
the relevant mixin(s) alongside `VultronEvent`. Updated all 7 use-case modules
to access domain properties instead of generic names.

**Source files changed**:

- `vultron/core/models/events/_mixins.py` — new file; 14 mixin classes
- `vultron/core/models/events/report.py` — mixin inheritance on 6 event classes
- `vultron/core/models/events/actor.py` — mixin inheritance on 3 event classes
- `vultron/core/models/events/embargo.py` — mixin inheritance on 6 event classes
- `vultron/core/models/events/case_participant.py` — mixin inheritance on 3 event classes
- `vultron/core/models/events/note.py` — mixin inheritance on 3 event classes
- `vultron/core/models/events/status.py` — mixin inheritance on 4 event classes
- `vultron/core/models/events/case.py` — mixin inheritance on `AddReportToCaseReceivedEvent`
- `vultron/core/use_cases/report.py`, `actor.py`, `embargo.py`, `case_participant.py`,
  `note.py`, `status.py`, `case.py` — all generic field references replaced

### Test results

984 passed, 5581 subtests passed.

---

## TECHDEBT-36 — Centralize `_make_payload()` test helper (COMPLETE 2026-03-24)

**Goal**: Remove 5 duplicate local `_make_payload(activity, **extra_fields)` functions from
test files in `test/core/use_cases/` and replace with the shared `make_payload` pytest
fixture already defined in `test/core/use_cases/conftest.py`.

**Approach**: Removed the local function definition from each of the 5 affected test files.
Removed the now-unused `from vultron.wire.as2.extractor import extract_intent` module-level
import from 3 files (`test_status_use_cases.py`, `test_note_use_cases.py`,
`test_case_use_cases.py`). Added `make_payload` as a fixture parameter to all 37 test
methods that previously called the local function.

**Source files changed**:

- `test/core/use_cases/test_status_use_cases.py` — removed local def, updated 7 test methods
- `test/core/use_cases/test_actor_use_cases.py` — removed local def, updated 13 test methods
- `test/core/use_cases/test_note_use_cases.py` — removed local def, updated 6 test methods
- `test/core/use_cases/test_case_use_cases.py` — removed local def, updated 6 test methods
- `test/core/use_cases/test_embargo_use_cases.py` — removed local def, updated 11 test methods

### Test results

985 passed, 5581 subtests passed.

---

## TECHDEBT-38 — Fix `outbox_handler` crash on missing actor / BUG-001 (COMPLETE 2026-03-24)

**Note**: The code fix (early `return` in `outbox_handler.py` when actor is `None`) was
already applied during OX-1.4 work. This entry records that the plan item was verified
and checked off. No code changes needed.

### Test results

985 passed, 5581 subtests passed.

---

## BUG-001: `outbox_handler` early-return fix

**Issue**: `outbox_handler` logged a warning when `dl.read(actor_id)` returned
`None` but did not return early. The subsequent `while actor.outbox.items:` line
raised `AttributeError: 'NoneType' object has no attribute 'outbox'`.

**Root cause**: Missing `return` statement after the `logger.warning(...)` call
in the `if actor is None` guard.

**Fix**: Added `return` immediately after the warning log in
`vultron/adapters/driving/fastapi/outbox_handler.py`.

**Test**: Added `test_outbox_handler_returns_early_when_actor_not_found` to
`test/api/v2/backend/test_outbox.py` to verify no exception is raised and the
warning is logged when the actor is not found.

---

## TECHDEBT-32 / TECHDEBT-32b — DataLayer boundary audit and core adapter import removal (COMPLETE 2026-03-24)

### What was done

**TECHDEBT-32 (research)**: Audited the `core`/`DataLayer` boundary for layer
violations. Findings written to `notes/datalayer-refactor.md`.

Key findings:

1. **Core violations** (CS-05-001): `vultron/core/use_cases/triggers/embargo.py`
   and `vultron/core/use_cases/triggers/_helpers.py` both imported
   `object_to_record` from `vultron.adapters.driven.db_record`. 5 call sites
   used `dl.update(obj.as_id, object_to_record(obj))`.
2. **Redundant core helper**: `save_to_datalayer()` in
   `vultron/core/behaviors/helpers.py` duplicated `dl.save()` using
   `StorableRecord`; used in BT nodes (`case/nodes.py`, `report/nodes.py`).
3. **Wire violation** (separate task TECHDEBT-32c): `rehydration.py` imports
   `get_datalayer` from the TinyDB adapter as a fallback.
4. `Record`/`StorableRecord` hierarchy is architecturally sound — no changes
   needed. `find_in_vocabulary` usages are all in adapter or wire layers.

**TECHDEBT-32b (code fix)**: Standardised on `dl.save(obj)` across all core code:

- Removed `object_to_record` import from `triggers/embargo.py` and
  `triggers/_helpers.py`. Replaced 5 `dl.update(..., object_to_record(...))` calls
  with `dl.save(obj)`.
- Replaced 4 `save_to_datalayer(self.datalayer, obj)` calls in BT nodes
  (`case/nodes.py`, `report/nodes.py`) with `self.datalayer.save(obj)`.
- Deleted `save_to_datalayer()` function from `helpers.py`.
- Removed now-unused `BaseModel` import from `helpers.py`.
- Added TECHDEBT-32c to plan for remaining wire-imports-adapter violation in
  `rehydration.py`.

### Lessons learned

The three `dl.save()` patterns (`object_to_record` + `dl.update`, `save_to_datalayer`,
and direct `dl.save`) all existed simultaneously, causing confusion. `dl.save()`
is now the canonical single pattern for persisting domain objects from core code.

### Test results

985 passed, 5581 subtests passed.

---

## TECHDEBT-32c — Remove get_datalayer fallback from wire/as2/rehydration.py

**Completed**: 2026-03-24

### What was done

Removed the adapter-layer import (`from vultron.adapters.driven.datalayer_tinydb
import get_datalayer`) from `vultron/wire/as2/rehydration.py`. The wire layer
must not import from a concrete adapter implementation.

- Made `dl: DataLayer` a required positional parameter in `rehydrate()`;
  removed the `None` default and the fallback `get_datalayer()` call.
- Updated three adapter-layer callers to pass `dl` explicitly:
  `vultron/adapters/driving/cli.py`,
  `vultron/adapters/driving/fastapi/routers/datalayer.py`,
  `vultron/adapters/driving/fastapi/inbox_handler.py`.
- Removed 25 legacy `monkeypatch.setattr(rehydration.get_datalayer, ...)` stubs
  from 6 test files under `test/core/use_cases/` — these were defensive patches
  for a fallback that no longer exists.
- Updated test mock in `test/api/v2/backend/test_inbox_handler.py` to accept
  `dl` keyword argument.

### Lessons learned

The "all production callers already pass `dl` explicitly" note in the plan was
incorrect — three adapter-layer callers were not passing `dl`. The fix required
updating callers in addition to removing the fallback. Always verify caller
state before relying on plan notes about external-facing APIs.

### Test results

985 passed, 5581 subtests passed.

---

## TECHDEBT-34 — EM state transition guards (2026-03-24)

**Task**: Verify and add guards to unguarded direct `em_state =` assignments
in `vultron/core/`.

### What was done

Audited all direct `em_state =` and `rm_state =` assignments in
`vultron/core/use_cases/` and `vultron/core/behaviors/`.

**EM sites addressed (3 unguarded `em_state = EM.ACTIVE`):**

1. `SvcEvaluateEmbargoUseCase` (`triggers/embargo.py`) — trigger-side: replaced
   direct assignment with `EMAdapter` + `create_em_machine()` + `adapter.accept()`
   pattern. `MachineError` now raises `VultronConflictError`. Consistent with
   `SvcProposeEmbargoUseCase` and `SvcTerminateEmbargoUseCase`.

2. `AddEmbargoEventToCaseReceivedUseCase` (`embargo.py`) — receive-side: added
   `is_valid_em_transition()` check with WARNING log on non-standard transition.
   Proceeds regardless (documented justification: state-sync override when
   local state lags behind sender's state).

3. `AcceptInviteToEmbargoOnCaseReceivedUseCase` (`embargo.py`) — receive-side:
   same pattern as #2.

**RM sites (no changes needed):** All `rm_state=RM.XXX` in core are
constructor arguments for new `VultronParticipantStatus` objects — initial-state
constructions, not transitions. The `append_rm_state()` method already enforces
`is_valid_rm_transition()` for all state-mutation paths.

Added `is_valid_em_transition` import to `embargo.py`.

Updated 2 existing tests to start from `EM.PROPOSED` (correct pre-condition
for the `PROPOSED → ACTIVE` transition). Added 3 new tests:

- `test_add_embargo_event_to_case_warns_on_non_standard_transition`
- `test_accept_invite_to_embargo_warns_on_non_standard_transition`
- `test_evaluate_embargo_raises_conflict_when_em_state_invalid`

### Test results

988 passed, 5581 subtests passed.

---

## TECHDEBT-39 — Consolidate duplicate participant RM state helper functions (OPP-05)

**Date**: 2026-03-24

**What was done**: Removed the module-level `_find_and_update_participant_rm()`
wrapper function from `vultron/core/behaviors/report/nodes.py`. This function
was a thin BT adapter that called `update_participant_rm_state()` from
`vultron/core/use_cases/triggers/_helpers.py` and converted its bool result
to a py_trees `Status`. Both BT node `update()` methods
(`TransitionParticipantRMtoAccepted` and `TransitionParticipantRMtoDeferred`)
now call `update_participant_rm_state()` directly with inline bool→Status
conversion and exception handling. Also removed the redundant local
`from vultron.core.states.rm import RM` imports inside each `update()` method,
since `RM` is already imported at module level.

There is now exactly one implementation of the "append a new participant RM
status" operation (`update_participant_rm_state()` in `_helpers.py`), used by
both the BT nodes and the trigger use cases.

### Test results

988 passed, 5581 subtests passed.

---

## TECHDEBT-35 — VultronEvent rich-object architectural fix

**Completed**: PRIORITY-80 phase.

### Problem

`VultronEvent` was designed to be the core-layer parallel of AS2 `Activity`
(as rich structurally), but was implemented as a flat DTO carrying only ID
strings (`object_id`, `target_id`, etc.). Concrete subclasses layered typed
domain object fields (`report: VultronReport`, `case: VultronCase`, etc.)
alongside the flat ID fields — two parallel representations that prevented the
mixins from providing clean rich-object access.

### Changes

- **`vultron/core/models/events/base.py`**: Replaced 14 flat ID/type string
  fields on `VultronEvent` with 7 rich `VultronObject | None` fields:
  `object_`, `target`, `context`, `origin`, `inner_object`, `inner_target`,
  `inner_context`. Added derived `@property` for all 14 old fields (backward
  compat for use-case code). `object_` uses a trailing underscore because
  `object` is a Python built-in.

- **`vultron/core/models/events/_mixins.py`**: Added rich `foo` property to
  every mixin alongside the existing `foo_id` property. Properties access
  `self.object_`, `self.target`, `self.context`, etc. with domain-typed hints
  under `TYPE_CHECKING`. Added `from __future__ import annotations` to support
  forward references.

- **Concrete event subclasses** (`report.py`, `case.py`, `embargo.py`,
  `note.py`, `status.py`, `case_participant.py`, `actor.py`): Removed all
  explicit typed domain object fields (`report: VultronReport`,
  `case: VultronCase`, `embargo: VultronEmbargoEvent`, `participant`,
  `note`, `status`). These are now provided by mixin properties. Kept
  explicit `activity: VultronActivity` redeclarations on subclasses that
  require it (existing approach, no `HasActivityMixin` introduced).

- **`vultron/wire/as2/extractor.py`**: Updated `_build_domain_kwargs()` to
  populate `object_=<domain obj>` instead of per-semantic keys (`report=`,
  `case=`, `embargo=`, etc.). Added `_to_domain_obj()` helper to wrap bare
  AS2 references as minimal `VultronObject` instances. Updated the constructor
  call to use the new rich field names; removed all flat `_id`/`_type` kwargs.

- **`test/core/use_cases/test_report_use_cases.py`**: Updated 3 event
  constructor calls from `object_id=..., report=VultronReport(...)` style
  to `object_=VultronReport(...)`.

### Test results

988 passed, 5581 subtests passed.

---

## ACT-2: Per-Actor DataLayer Isolation (ADR-0012)

**Priority**: 100 (highest open task at time of implementation)

### Summary

Implemented Option B (TinyDB namespace prefix per actor) from ADR-0012.
Each actor's tables are prefixed `{actor_id}_*` in the same TinyDB file.
Activity objects are stored in the shared DataLayer for cross-actor
accessibility; inbox/outbox queues are in the actor-scoped DataLayer.

### Key design decisions

- **Activity objects → shared DL**: All activities are stored in the shared
  (unprefixed) DataLayer so rehydration and cross-actor use cases work.
- **Inbox/outbox queues → actor-scoped DL**: Queue records hold only the
  `activity_id` string in `{actor_id}_inbox` / `{actor_id}_outbox` tables.
- **Inbox visibility record → actor object in shared DL**: `post_actor_inbox`
  also appends the activity ID to `actor.inbox.items` in the shared DL actor
  record (persistent received-log, never cleared by the handler).
- **`_shared_dl()` wrappers**: Prevent FastAPI from injecting the `actor_id`
  path parameter into `get_datalayer()` calls in all routers.
- **`_actor_dl()` in trigger routes returns shared DL**: Trigger use cases
  need the shared DL (actors, offers, reports are all there).

### Files modified

- `vultron/adapters/driven/datalayer_tinydb.py`: actor_id prefix, `_my_tables()`,
  inbox/outbox methods, `get_datalayer(actor_id)` factory, `reset_datalayer()`
- `vultron/core/ports/datalayer.py`: 6 inbox/outbox Protocol methods
- `vultron/adapters/driving/fastapi/inbox_handler.py`: accepts `actor_dl` param
- `vultron/adapters/driving/fastapi/outbox_handler.py`: uses `dl.outbox_list/pop`
- `vultron/adapters/driving/fastapi/routers/actors.py`: `_shared_dl()`, inbox
  visibility record update, actor-scoped queue management
- `vultron/adapters/driving/fastapi/routers/datalayer.py`: `_shared_dl()`
- `vultron/adapters/driving/fastapi/routers/trigger_{report,case,embargo}.py`:
  `_actor_dl()` returns shared DL
- `vultron/demo/utils.py`: `init_actor_ios()` is no-op
- `test/adapters/driven/test_datalayer_isolation.py`: 26 new isolation tests

### Test results

1014 passed, 5581 subtests passed.

---

## Refresh #51 — VCR-014 + TECHDEBT-37 (2026-03-25)

### Tasks completed

- **VCR-014**: Removed `vultron/api/v2/data/actor_io.py`. The global in-memory
  `ACTOR_IO_STORE` is fully superseded by the DataLayer inbox/outbox methods
  (`inbox_list/pop/append`, `outbox_list/pop/append`) added in ACT-2.
  Removed the `init_actor_io` import and call from all test fixtures.
  Deleted `test/api/v2/data/test_actor_io.py` and `test/api/v2/data/conftest.py`.

- **TECHDEBT-37**: Migrated all tests from `test/api/` to the canonical layout:
  - `test/api/v2/backend/test_inbox_handler.py` →
    `test/adapters/driving/fastapi/test_inbox_handler.py`
  - `test/api/v2/backend/test_outbox.py` →
    `test/adapters/driving/fastapi/test_outbox.py`
  - `test/api/v2/backend/test_trigger_services.py` →
    `test/adapters/driving/fastapi/test_trigger_services.py`
  - `test/api/v2/conftest.py` →
    `test/adapters/driving/fastapi/conftest.py`
  - `test/api/v2/test_v2_api.py` →
    `test/adapters/driving/fastapi/test_api.py`
  - `test/api/v2/routers/conftest.py` →
    `test/adapters/driving/fastapi/routers/conftest.py`
  - `test/api/v2/routers/test_actors.py` →
    `test/adapters/driving/fastapi/routers/test_actors.py`
  - `test/api/v2/routers/test_datalayer_serialization.py` →
    `test/adapters/driving/fastapi/routers/test_datalayer_serialization.py`
  - `test/api/v2/routers/test_datalayer.py` →
    `test/adapters/driving/fastapi/routers/test_datalayer.py`
  - `test/api/v2/routers/test_health.py` →
    `test/adapters/driving/fastapi/routers/test_health.py`
  - `test/api/v2/routers/test_trigger_{report,case,embargo}.py` →
    `test/adapters/driving/fastapi/routers/test_trigger_{report,case,embargo}.py`
  - `test/api/v2/datalayer/conftest.py` →
    `test/adapters/driven/conftest.py`
  - `test/api/v2/datalayer/test_db_record.py` →
    `test/adapters/driven/test_db_record.py`
  - `test/api/v2/datalayer/test_tinydb_backend.py` →
    `test/adapters/driven/test_tinydb_backend.py`
  - `test/api/test_reporting_workflow.py` →
    `test/core/use_cases/test_reporting_workflow.py`
  - `test/api/` directory removed.

### Files modified

- `vultron/api/v2/data/actor_io.py`: deleted
- `test/api/` directory: deleted (all tests relocated)
- `test/adapters/driving/` directory: created with `__init__.py`
- `test/adapters/driving/fastapi/` directory: created with all migrated tests
- `test/adapters/driving/fastapi/routers/` directory: created with all
  migrated router tests
- `test/adapters/driven/conftest.py`: created (from datalayer/conftest.py)
- `test/adapters/driven/test_db_record.py`: created
- `test/adapters/driven/test_tinydb_backend.py`: created
- `test/core/use_cases/test_reporting_workflow.py`: created

### Test results

998 passed, 5581 subtests passed.

---

## ACT-3 — Per-actor DataLayer for trigger endpoints (2026-03-25)

**Task**: Update `get_datalayer` dependency and all handler tests to use
per-actor DataLayer fixtures (ADR-0012 DI-1 closure lambda strategy).

### What was done

- Updated `_actor_dl` FastAPI dependency in all three trigger routers to call
  `get_datalayer(actor_id)` instead of the shared `get_datalayer()`:
  - `vultron/adapters/driving/fastapi/routers/trigger_case.py`
  - `vultron/adapters/driving/fastapi/routers/trigger_report.py`
  - `vultron/adapters/driving/fastapi/routers/trigger_embargo.py`
- Refactored trigger test fixtures in all three test files to use a combined
  `actor_and_dl` fixture that creates the actor in-memory first, then
  instantiates a `TinyDbDataLayer(db_path=None, actor_id=actor.as_id)` scoped
  to that actor's ID, and persists the actor into it.  The `actor` and `dl`
  fixtures unpack from `actor_and_dl`.
- Updated `test_trigger_validate_report_uses_injected_datalayer` to use the
  per-actor `dl` fixture instead of the shared `datalayer` fixture.
- Removed unused `object_to_record` import from `test_trigger_report.py`.

### Lessons learned

- The "actor before DataLayer" combined-fixture pattern (`actor_and_dl`) solves
  the chicken-and-egg problem of needing the actor's `as_id` to create a
  scoped DataLayer, while still allowing all downstream fixtures to depend on
  both `actor` and `dl` independently.
- The `client_triggers` override `lambda: dl` continues to work after the
  production change because FastAPI `dependency_overrides` replaces the entire
  dependency callable, bypassing the `actor_id = Path(...)` parameter.

### Test results

998 passed, 5581 subtests passed.

---

## OX-1.1/1.2/1.3 — Outbox delivery implementation (2026-03-25)

**Tasks**: OX-1.1 (local/remote delivery), OX-1.2 (background delivery after
inbox processing), OX-1.3 (inbox idempotency).

**Architecture note**: Each actor runs as an isolated process/container.
Outbox delivery uses HTTP POST to recipient inbox URLs — not direct DataLayer
access. OX-1.3 idempotency is enforced at the receiving inbox endpoint.

### What was done

**`vultron/adapters/driven/delivery_queue.py`** (OX-1.1):

- Replaced stub `emit()` with real HTTP POST delivery using `httpx`.
- Each recipient inbox URL is derived as `{actor_uri}/inbox/` (ActivityPub
  convention).
- Per-recipient failures are logged at ERROR and swallowed so one unreachable
  actor never blocks others.

**`vultron/adapters/driving/fastapi/outbox_handler.py`** (OX-1.1):

- Added `_extract_recipients(activity)` helper — deduplicates `to`/`cc`/
  `bto`/`bcc` fields, handles both string IDs and embedded actor objects.
- Rewrote `handle_outbox_item(actor_id, activity_id, dl, emitter)` — reads
  activity from DataLayer, extracts recipients, calls `emitter.emit()`.
- Updated `outbox_handler(actor_id, dl, shared_dl=None, emitter=None)` to
  accept a shared DataLayer (for reading activity objects) and injectable
  emitter (defaults to `DeliveryQueueAdapter()`).

**`vultron/adapters/driving/fastapi/inbox_handler.py`** (OX-1.2):

- Added `await outbox_handler(actor_id, queue_dl, shared_dl=dl)` at end of
  `inbox_handler` so outbound activities generated during inbox processing
  are delivered immediately after (OX-03-002).

**`vultron/adapters/driving/fastapi/routers/actors.py`** (OX-1.3):

- Added duplicate-activity check in `post_actor_inbox`: if the activity ID is
  already in the actor's inbox queue, returns 202 immediately without
  re-scheduling processing (OX-06-001).
- Updated `post_actor_outbox` to pass shared `dl` as `shared_dl` to
  `outbox_handler`.

**Tests**:

- Updated `test_outbox.py`: new signatures, 6 new delivery-logic tests
  covering `_extract_recipients`, skip-on-no-activity, skip-on-no-recipients,
  deduplication, embedded objects, and emit call verification.
- Updated `test_inbox_handler.py`: added `outbox_list.return_value = []` to
  prevent mock DL issues with the new OX-1.2 outbox trigger.

### Lessons learned

- Outbox delivery must use HTTP POST (not DataLayer access) to support
  isolated-process actors. Each actor manages its own DataLayer; cross-actor
  delivery must go through the HTTP API.
- OX-1.3 idempotency belongs at the inbox endpoint, not the delivery side —
  delivery adapters have no access to remote actor DataLayers.
- The `shared_dl` / `emitter` injectable parameters on `outbox_handler` keep
  the handler testable without requiring real HTTP or real DataLayers.

### Test results

1004 passed, 5581 subtests passed.

---

## CA-1 + CA-3: CaseActor broadcast on case update (CM-06-001/CM-06-002)

**Date**: 2026-03-20
**Phase**: PRIORITY-200 (Case Actor)
**Status**: COMPLETE

### Summary

Implemented the CaseActor broadcast requirement (CM-06-001/CM-06-002):
after `UpdateCaseReceivedUseCase` saves a case update, it now emits an
`Announce` activity from the CaseActor to all active case participants.

### Changes

**`vultron/core/models/activity.py`**:

- Added `to: list[str] | None = None` and `cc: list[str] | None = None`
  addressing fields to `VultronActivity` so broadcast activities carry
  recipient information for downstream delivery routing.

**`vultron/core/ports/datalayer.py`**:

- Added `by_type(as_type: str) -> dict[str, dict]` to the `DataLayer`
  Protocol so core use cases can query objects by AS2 type without
  importing adapter-layer code.

**`vultron/core/use_cases/case.py`**:

- Added `_broadcast_case_update()` private method to
  `UpdateCaseReceivedUseCase`.
- After saving the updated case, calls `_broadcast_case_update()` which:
  1. Looks up the CaseActor via `dl.by_type("Service")` filtered by
     `context == case_id`.
  2. Collects all participant actor IDs from
     `case.actor_participant_index.keys()`.
  3. Creates a `VultronActivity(as_type="Announce", actor=case_actor_id,
     as_object=case_id, to=participant_ids)` and persists it.
  4. Appends the broadcast activity ID to the CaseActor's
     `outbox.items` and saves the CaseActor.
- Broadcast also fires when the update contains only a reference (no
  fields to apply), consistent with CM-06-001 applying to any case update.

**`test/core/use_cases/test_case_use_cases.py`**:

- Added four new broadcast tests (CA-3):
  - `test_update_case_broadcasts_announce_to_participants` — happy path
  - `test_update_case_no_broadcast_when_no_case_actor` — graceful no-op
  - `test_update_case_no_broadcast_when_no_participants` — graceful no-op
  - `test_update_case_broadcast_includes_all_participants` — multi-participant

### Test results

1008 passed, 5581 subtests passed (up from 1004).

### Lessons learned

- `by_type` was already implemented on `TinyDbDataLayer` but missing from
  the `DataLayer` Protocol; adding it to the port was the minimal change
  to keep core code architecture-compliant.
- The broadcast fires even for reference-only updates (no field changes),
  since CM-06-001 does not restrict notification to field-changing updates.
- Actual HTTP delivery of the broadcast to participant inboxes requires
  the CaseActor's per-actor outbox queue to be populated and the
  `outbox_handler` to be triggered. Writing to `outbox.items` (the shared
  DL actor object) records the broadcast for history/visibility but does
  not trigger immediate delivery — consistent with the existing pattern in
  trigger use cases and `CloseCaseReceivedUseCase`.

---

## CA-2: Action Rules Endpoint (PRIORITY-200)

**Completed**: Implemented `GET /actors/{case_actor_id}/action-rules?participant={actor_id}`
endpoint returning valid CVD actions for a named participant given the current
combined case state (RM, EM, CS_vfd, CS_pxa).

**Files changed**:

- `vultron/core/use_cases/action_rules.py` (new): `ActionRulesRequest` model
  and `GetActionRulesUseCase` class. Resolves CaseActor → VulnerabilityCase →
  CaseParticipant, reads per-participant RM/VFD state and shared case EM/PXA
  state, builds the 6-char CS state string, and returns valid CVD actions via
  `potential_actions.action()`.
- `vultron/adapters/driving/fastapi/routers/actors.py`: Added
  `GET /{case_actor_id}/action-rules` endpoint (positioned before inbox to
  avoid path conflicts).
- `test/core/use_cases/test_action_rules.py` (new): Unit tests for
  `GetActionRulesUseCase` covering happy path, default states, error paths,
  and EM state variations.
- `test/adapters/driving/fastapi/routers/test_actors.py`: Added endpoint
  integration tests (200, 404, 422).

**Specs implemented**: CM-07-001, CM-07-002, CM-07-003, AR-07-001, AR-07-002.

---

## CA-2 follow-up: actor-first case-scoped action-rules endpoint

**Completed**: Reworked the CA-2 action-rules contract to use the final
actor-first, case-scoped route:
`GET /actors/{actor_id}/cases/{case_id}/action-rules`.

**What changed**:

- `vultron/adapters/driving/fastapi/routers/actors.py`: replaced the prior
  action-rules shape with the actor-first case-scoped endpoint.
- `vultron/core/use_cases/action_rules.py`: simplified `ActionRulesRequest` to
  `(case_id, actor_id)` and resolved the matching `CaseParticipant`
  internally via `actor_participant_index` with a fallback scan of
  `case.case_participants`.
- `vultron/core/models/protocols.py`: tightened the protocol typing used by
  the action-rules use case so the new logic remains core-friendly and avoids
  wire imports.
- `test/core/use_cases/test_action_rules.py` and
  `test/adapters/driving/fastapi/routers/test_actors.py`: updated unit and
  router coverage to validate the actor/case contract, including 404 behavior
  for unknown cases and actors not participating in the selected case.
- `specs/case-management.md` and `specs/agentic-readiness.md`: updated to
  document the final actor-first case-scoped endpoint and the internal
  actor→participant resolution behavior.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/`
- `markdownlint-cli2 --fix --config .markdownlint-cli2.yaml "**/*.md"`
- `uv run pytest --tb=short 2>&1 | tail -5` → `1021 passed, 5581 subtests passed`

---

## QUALITY-1 — Treat pytest warnings as errors (2026-03-26)

**Task**: Configure pytest to treat warnings as errors, fix any existing
warnings surfaced by this change.

**What was done**:

- Added `filterwarnings = ["error"]` to `[tool.pytest.ini_options]` in
  `pyproject.toml` (per `specs/tech-stack.md` IMPL-TS-07-006).
- Fixed `ResourceWarning: unclosed file 'mydb.json'` in
  `vultron/adapters/driven/datalayer_tinydb.py`:
  - Added `TinyDbDataLayer.close()` method that calls `self._db.close()` to
    explicitly release TinyDB file handles.
  - Updated `reset_datalayer()` to call `.close()` on each instance before
    dropping references, preventing unclosed file warnings when instances are
    garbage-collected.
- Updated `.github/skills/run-tests/SKILL.md` to document the warnings-as-errors
  behaviour and the requirement not to suppress warnings without fixing root causes.
- Recorded two pre-existing bugs in `plan/BUGS.md`:
  - BUG-2026032602: `uv run` fails due to `snapshot/Q1-2026` git tag (workaround:
    use `.venv/bin/pytest` directly).
  - BUG-2026032603: Test ordering dependency in `test_datalayer_isolation.py`
    (passes in full suite; fails when run in isolation due to vocabulary registry
    not being populated).

**Validation**:

- `.venv/bin/black vultron/ test/ && .venv/bin/flake8 vultron/ test/`
- `.venv/bin/pytest --tb=short 2>&1 | tail -5` → `1026 passed, 5581 subtests passed`

---

## BUG-2026032603 — Test ordering dependency in test_datalayer_isolation.py (2026-03-26)

**Issue**: `TestRecordIsolation::test_two_actors_can_store_same_id_independently`
failed when run in isolation with `ValueError: Type 'Note' not found in vocabulary
for Record conversion`. Passed in the full suite due to vocabulary side-effect imports.

**Root cause**: Two related issues:

1. `test/adapters/driven/conftest.py` imported `as_Note` only inside a fixture
   function body (local import), so `Note` was never registered in the vocabulary
   unless that fixture was used.
2. `_object_from_storage` in `datalayer_tinydb.py` caught `ValidationError` but
   not `ValueError`, so the vocabulary lookup failure propagated unchecked.

**Resolution**:

- Moved `as_Note` import to module level in `test/adapters/driven/conftest.py`
  so the vocabulary is always populated when the test package loads.
- Broadened the exception catch in `_object_from_storage` to include `ValueError`
  as a defensive measure for unknown vocabulary types.

**Lesson**: Test helper types (like `type_="Note"`) that require vocabulary
registration must be accompanied by a module-level import of the corresponding
class. Local imports inside fixtures do not guarantee registration order.

---

## BUG-2026032602 — uv run fails due to snapshot/Q1-2026 git tag (2026-03-26)

**Issue**: `uv run pytest` (and all `uv run <tool>` commands) failed to build
the package with `AssertionError` in `vcs_versioning`.

**Root cause**: The local tag `snapshot-2026Q1` is "externally known as"
`snapshot/Q1-2026` (its remote alias). `git describe --dirty --tags --long`
returned `snapshot/Q1-2026-...-...`. The `vcs_versioning` backend (used by
`setuptools-scm` in the `uv` build environment) tried to parse `snapshot/Q1-2026`
against the `tag_regex`, got `None`, and raised `AssertionError`.
`fallback_version` was not reached because the code path raises rather than
returning `None`.

**Resolution**: Added `git_describe_command` to `[tool.setuptools_scm]` in
`pyproject.toml` to pass `--match v[0-9]*` to `git describe`. This restricts
git describe to semver-style `v<N>.*` tags only, skipping snapshot and branch
tags. Also added `fallback_version = "0.0.0+dev"` for future resilience.

**Lesson**: When a git repo has non-semver tags near HEAD (especially tags with
external remote aliases), setuptools_scm/vcs_versioning may find and fail to
parse them. Set `git_describe_command` with an explicit `--match` glob in
`[tool.setuptools_scm]` to guard against this.

---

## VSR-ERR-1 + SM-GUARD-1 + BUG-FLAKY-1 (2026-03-30)

**Branch**: p251  **Tests**: 1027 passed, 5581 subtests

### What was done

Three grouped PRIORITY-250 tasks completed in one commit:

**VSR-ERR-1 — Rename VultronConflictError**:

- Renamed `VultronConflictError` → `VultronInvalidStateTransitionError` in
  `vultron/errors.py` per `specs/state-machine.md` SM-04-002.
- Retained `VultronConflictError` as a deprecated alias.
- Updated all 5 raise sites in `vultron/core/use_cases/triggers/embargo.py`
  (4 sites) and `triggers/report.py` (1 site) to use the new name.
- Added `logger.warning(...)` before each raise as required by SM-04-002.
- Updated `vultron/adapters/driving/fastapi/errors.py` isinstance check.
- Updated `vultron/core/use_cases/triggers/__init__.py` docstring.
- Updated `test/core/use_cases/test_embargo_use_cases.py`.

**SM-GUARD-1 — Export EM_NEGOTIATING**:

- Added `EM_NEGOTIATING` to exports in `vultron/core/states/__init__.py`.
- Replaced inline `[EM.PROPOSED, EM.REVISE]` in
  `vultron/bt/embargo_management/transitions.py` with `list(EM_NEGOTIATING)`.

**BUG-FLAKY-1 — Fix flaky test_remove_embargo**:

- Fixed `test/wire/as2/vocab/test_vocab_examples.py::test_remove_embargo` by
  extracting the embargo from `activity.as_object` rather than independently
  calling `examples.embargo_event(days=90)` (which generates a new time-based
  ID on each call). The test now asserts `embargo.context == case.as_id`.

---

## REORG-1 — Reorganize `vultron/core/use_cases/` (COMPLETE 2026-03-30)

Reorganized `vultron/core/use_cases/` into clearer sub-packages per
`specs/use-case-organization.md` UC-ORG-01-001 through UC-ORG-04-001.

**Source moves (via `git mv`):**

- 8 received-handler modules (`actor.py`, `case.py`, `case_participant.py`,
  `embargo.py`, `note.py`, `report.py`, `status.py`, `unknown.py`) moved to
  `vultron/core/use_cases/received/`
- `action_rules.py` moved to `vultron/core/use_cases/query/`
- `_helpers.py` retained at root (shared by `received/` and `triggers/`)

**Test moves (via `git mv`):**

- 8 received test files moved to `test/core/use_cases/received/` and renamed
  to drop the `_use_cases` suffix
- `test_action_rules.py` moved to `test/core/use_cases/query/`

**Import updates:**

- `use_case_map.py` — all 8 imports updated to `received.*`; stale
  `SEMANTICS_HANDLERS` alias and `api/v2` docstring comment removed
- `vultron/adapters/driving/fastapi/routers/actors.py` — `action_rules` import
  updated to `query.action_rules`
- All moved test files — imports updated to new paths
- `test/core/use_cases/test_reporting_workflow.py` and
  `test/core/ports/test_use_case.py` — imports updated in place

**New files:** `received/__init__.py`, `query/__init__.py`,
`test/core/use_cases/received/__init__.py`,
`test/core/use_cases/query/__init__.py`, and `vultron/core/use_cases/README.md`
documenting the trigger→received→sync information flow.

**Tests:** 1027 passed, 5581 subtests (unchanged from before).

**Commit:** 3337e7e0

---

## SECOPS-1 — CI Security: ADR + Automated SHA-Pin Verification Test (2026-03-30)

**Task:** SECOPS-1 (PRIORITY-250 pre-300 cleanup)

**What was done:**

- Created `docs/adr/0014-sha-pin-github-actions.md`: ADR documenting the
  SHA-pinning policy (all `uses:` references must be pinned to a 40-char commit
  SHA with an inline human-readable version comment), the use of Dependabot as
  the primary maintenance mechanism, and the automated test as the continuous
  enforcement mechanism. References CI-SEC-04-001.
- Added ADR-0014 to `docs/adr/index.md`.
- Created `test/ci/__init__.py` and `test/ci/test_workflow_sha_pinning.py`:
  53 parametrised pytest tests covering every `uses:` line across all 6
  `.github/workflows/*.yml` files. Tests verify:
  - CI-SEC-01-001: reference is pinned to a full 40-hex-character SHA
  - CI-SEC-01-002: SHA line carries an inline version comment (e.g., `# v4.1.0`)

**Tests:** 1080 passed (+53 new), 5581 subtests passed.

**Commit:** 3e5b3079

---

## DOCMAINT-1 — Update outdated notes/ files (COMPLETE 2026-03-30)

**Task:** DOCMAINT-1 (PRIORITY-250 pre-300 cleanup)

**What was done:**

Updated four notes files to replace outdated forward-looking language with
current implementation status:

- **`notes/activitystreams-semantics.md`** (~line 333): Updated "CaseActor
  broadcast is not yet implemented" to reflect implementation in
  `UpdateCaseReceivedUseCase._broadcast_case_update()` (completed in
  PRIORITY-200 CA-2, 2026-03-25).

- **`notes/state-machine-findings.md`** (Section 9 "Completion Status"):
  Removed the warning about fictional commit SHAs and the table of fictional
  commit hashes. Replaced with an accurate per-item status table referencing
  actual implementation phases (P90-1–P90-5, TECHDEBT-32b, TECHDEBT-39).
  Updated "Deferred (explicit)" section: OPP-05 is now done (TECHDEBT-39,
  2026-03-24), full STATUS dict deprecation is done (P90-1/P90-4); only
  OPP-06 (VFD/PXA machines) remains deferred.

- **`notes/datalayer-refactor.md`** (TECHDEBT-32b/32c sections): Marked
  TECHDEBT-32b as completed (2026-03-24) with a summary of what was done;
  marked TECHDEBT-32c as pending with a clearer label.

- **`notes/codebase-structure.md`** (multiple sections):
  - Updated "Top-Level Module Reorganization Status": removed stale references
    to `vultron/api/v2/backend/handler_map.py`, `vultron/dispatcher_errors.py`,
    `vultron/behavior_dispatcher.py`, and `vultron/enums.py` (all removed/
    relocated); added their canonical current locations.
  - "API Layer Architecture": Renamed from "Future Refactoring" to
    "Historical (Completed in VCR Batch B / P65)"; replaced old path table
    with current canonical locations.
  - "Handlers Module Structure": Renamed to "Use-Case Module Structure
    (Completed — REORG-1)"; updated to describe current
    `vultron/core/use_cases/` layout.
  - TECHDEBT-11: Updated to note that new test directories exist but old ones
    have not been removed yet.
  - TECHDEBT-12: Marked resolved (trigger_services removed in VCR Batch D).
  - "Known Gap: Outbox Delivery Not Implemented": Replaced with "Resolved:
    Outbox Delivery (OX-1.0–1.4)".
  - "Resolved: app.py Root Logger Side Effect": Updated path from
    `vultron/api/v2/app.py` to `vultron/adapters/driving/fastapi/app.py`.
  - "Trigger Services Package": Replaced forward-looking migration plan with
    completed-status summary showing current canonical locations.
  - Fixed Object IDs section: `vultron/as_vocab/base/utils.py` →
    `vultron/wire/as2/vocab/base/utils.py`; `vultron/api/v2/routers/datalayer.py`
    → `vultron/adapters/driving/fastapi/routers/datalayer.py`.

**Tests:** 1080 passed, 5581 subtests passed (no code changes; docs only).

---

## SPEC-AUDIT-3 — Fix Stale Spec References (COMPLETE 2026-03-30)

**Task**: Relocate transient implementation notes from specs and fix outdated
stale references found during the 2026-03-30 gap analysis.

### Changes Made

**Stale test path references** — updated `test/api/v2/` → canonical current
paths in 9 spec files:

- `dispatch-routing.md`: `test/api/v2/backend/test_dispatch_routing.py`
  → `test/test_behavior_dispatcher.py`, `test/test_semantic_handler_map.py`
- `handler-protocol.md`: `test/api/v2/backend/test_handlers.py`
  → `test/core/use_cases/received/`, `test/test_semantic_handler_map.py`
- `error-handling.md`: `test/api/v2/backend/test_error_handling.py`
  → `test/adapters/driving/fastapi/test_error_handling.py` (future)
- `inbox-endpoint.md`, `message-validation.md`, `http-protocol.md`:
  `test/api/v2/routers/test_actors.py`
  → `test/adapters/driving/fastapi/routers/test_actors.py`
- `structured-logging.md`: `test/api/v2/test_logging.py`
  → `test/adapters/driving/fastapi/test_logging.py` (future)
- `observability.md`: `test/api/v2/routers/test_health.py`
  → `test/adapters/driving/fastapi/routers/test_health.py`
- `response-format.md`: `test/api/v2/backend/test_response_generation.py`
  → `test/adapters/driving/fastapi/test_response_generation.py` (future)
- `idempotency.md`: `test/api/v2/backend/test_idempotency.py`
  → `test/core/test_idempotency.py` (future)
- `outbox.md`: `test/api/v2/backend/test_outbox.py`
  → `test/adapters/driving/fastapi/test_outbox.py`

**`SEMANTIC_HANDLER_MAP` → `USE_CASE_MAP`** — updated in 3 spec files:

- `handler-protocol.md`: HP-03-001 description, verification section
- `semantic-extraction.md`: SE-05-002 requirement text, verification section

**`@verify_semantics` decorator** — removed/updated in 3 spec files:

- `behavior-tree-integration.md`: BT-04-001 verification criterion updated
  to reference `USE_CASE_MAP` dispatch
- `architecture.md`: ARCH-07-001 "current state" note updated to describe
  current dispatch-time validation via `USE_CASE_MAP`
- `testability.md`: TB-05-005 rationale updated to reference `USE_CASE_MAP`

**Stale implementation paths** — updated in 5 spec files:

- `code-style.md`: CS-05-001 updated core/app layer boundaries
  (`vultron/behavior_dispatcher.py` removed; `api/v2/*` → `vultron/adapters/`)
- `semantic-extraction.md`: Related section updated to current dispatcher path
- `error-handling.md`: Related section updated to `fastapi/errors.py`
- `outbox.md`: Related section updated to delivery_queue and outbox_handler
- `idempotency.md`: Implementation section updated to current DataLayer port
- `response-format.md`: Related section updated to core use_cases

**TB-04-001 test structure** — updated mirror paths in `testability.md`
to reflect current `test/adapters/`, `test/core/`, `test/wire/` layout.

**Tests:** 1080 passed, 5581 subtests passed (no code changes; docs only).

---

## NAMING-1 — Standardize `as_`-prefixed field names (2026-03-30)

**Task**: Rename all `as_`-prefixed Pydantic field names to the trailing-underscore
convention throughout the codebase (both wire layer and core layer).

**Changes**:

- Renamed 4 field names across 130 Python files (~2756 occurrences):
  - `as_id` → `id_`
  - `as_type` → `type_`
  - `as_object` → `object_`
  - `as_context` → `context_`
- Renames cover: field definitions, attribute accesses (`.as_id` etc.),
  keyword arguments (`as_id=...`), string references in `getattr`/`hasattr`
  calls, and docstrings/comments.
- Class names (`as_Activity`, `as_Object`, etc.) are **not** renamed.
- Pydantic field aliases (`validation_alias`, `serialization_alias`) are
  unchanged — JSON serialization and deserialization behavior is preserved.
- Updated `specs/code-style.md` CS-07-001 through CS-07-003 to reflect
  migration complete (MUST-level policy now).
- Updated `AGENTS.md` naming conventions, pattern-matching example, and
  all pitfall code snippets to use `id_`, `type_`, `object_`.

**Tests**: 1080 passed, 5581 subtests passed.

---

## SPEC-AUDIT-2 — RFC 2119 strength keyword migration (2026-03-30)

**Task**: Ensure every requirement line in `specs/` has an RFC 2119 keyword
on its first line, and remove keyword suffixes from section headers.

**Changes**:

- **176 keyword additions**: Requirement lines missing a keyword on the first
  line (keyword was on a wrapped continuation line, absent, or only in the
  section header) now have the keyword inserted immediately after the ID.
  Prefix-style keywords are parenthesised: `` `ID` (MUST) text ``.
  Naturally-embedded keywords (e.g. `All handlers MUST ...`) are left as-is.
- **293 header cleanups**: `## Section (MUST)` / `(SHOULD)` / `(MAY)` etc.
  suffixes removed from all `##` and `###` headers across 37 spec files.
  Removing headers that had identical base names (e.g. two `## Embargo Rules`
  sections previously separated by `(MUST)`/`(SHOULD)`) also resulted in
  31 duplicate-header merges in `vultron-protocol-spec.md` and `code-style.md`.
- **171 format fixes**: A second pass converted bare prefix keywords
  (`MUST text`) to the parenthesised form (`(MUST) text`) for visual
  clarity and to distinguish them from sentence-embedded keywords.

**Verification**:

- ``grep -rn "^\- `[A-Z]" specs/*.md | grep -v "MUST\|SHOULD\|..." → 0 hits``
- `grep -rh "^## \|^### " specs/*.md | grep "(MUST)\|(SHOULD)\|(MAY)"` → 0 hits
- `markdownlint-cli2`: 0 errors

**Tests**: 1080 passed, 5581 subtests (no code changes; docs only).

---

## SPEC-AUDIT-1 — Consolidation audit: eliminate redundant requirements (2026-03-30)

**Task**: Audit all `specs/` files to identify overlapping or duplicated
requirements; merge or cross-reference to eliminate maintenance-burden
redundancy.

**Changes**: Added 21 bidirectional cross-reference sub-bullets across 6
spec files, following the `ID-1 relationship ID-2` convention from
`specs/meta-specifications.md`.

### dispatch-routing.md ↔ handler-protocol.md

- `HP-02-001 depends-on DR-01-003` / `DR-01-003 is-dependency-of HP-02-001`:
  Handler semantic-type verification is fulfilled by the dispatcher lookup.
- `HP-02-002 refines DR-01-003` / `DR-01-003 is-refined-by HP-02-002`:
  Handler perspective on how the verification mechanism must behave.
- `HP-03-001 derives-from DR-02-001` / `DR-02-001 is-derived-by HP-03-001`:
  Handler discoverability requirement derives from the USE_CASE_MAP lookup.
- `HP-03-002 refines DR-02-002` / `DR-02-002 is-refined-by HP-03-002`:
  Registry key–type matching refines the completeness requirement.

### semantic-extraction.md → dispatch-routing.md

- `SE-05-002 derives-from DR-02-002` / `DR-02-002 is-derived-by SE-05-002`:
  Pattern→use-case coverage check derives from the USE_CASE_MAP completeness
  requirement.

### code-style.md ↔ tech-stack.md

- `CS-01-001 refines IMPL-TS-07-001` / reverse: code style requirement
  refines the authoritative Black tooling requirement.
- `CS-01-002 derives-from IMPL-TS-07-005` / reverse: CI formatting-check
  requirement derives from the parallel-jobs CI requirement.
- `CS-01-003 duplicates IMPL-TS-07-001/004/005` (and reverses): developer
  enforcement summary in code-style duplicates canonical tool requirements
  in tech-stack.
- `CS-01-006 duplicates IMPL-TS-07-002/003` (and reverses): static type
  enforcement in code-style duplicates canonical per-tool requirements in
  tech-stack.

### architecture.md ↔ code-style.md

- `CS-05-001 derives-from ARCH-01-001` / `ARCH-01-001 is-derived-by CS-05-001`:
  Code-style layer-separation import rule derives from the architecture
  layer-separation requirement.

**Verification**:

- `markdownlint-cli2`: 0 errors (453 files linted)
- No code changes; cross-references are docs-only additions.

**Tests**: 1080 passed, 5581 subtests (no code changes; docs only).

---

## SPEC-AUDIT-1 — Consolidation audit: eliminate redundant requirements (COMPLETE 2026-03-30)

*(Note: a partial cross-reference-only pass was made earlier in this session;
this entry records the completed elimination pass.)*

**Task**: Audit all `specs/` files to identify overlapping or duplicated
requirements; eliminate redundant requirements and cross-reference between
canonical and superseded items.

### Pairs audited

**`tech-stack.md` vs `code-style.md`** (canonical: `tech-stack.md` for
enforcement; `code-style.md` for style conventions):

- `CS-01-002` deprecated and superseded by `IMPL-TS-07-005`
- `CS-01-003` deprecated and superseded by `IMPL-TS-07-001`, `IMPL-TS-07-004`,
  `IMPL-TS-07-005`
- `CS-01-006` deprecated and superseded by `IMPL-TS-07-002`, `IMPL-TS-07-003`
- Added consolidation note to `code-style.md` header
- `IMPL-TS-07-001–005` updated with `supersedes` relationships (replacing
  `is-duplicated-by`)

**`dispatch-routing.md` vs `handler-protocol.md`** (canonical: dispatch-routing
for mechanism; handler-protocol for contract):

- Removed duplicate `**Implementation**:` notes from `HP-02-001` and
  `HP-03-001` (implementation details live in `dispatch-routing.md`)
- Replaced duplicate test assertions in `HP-02-001/002` and `HP-03-001/002`
  verification sections with pointers to `dispatch-routing.md` verification
  criteria
- All bidirectional `depends-on`/`is-dependency-of`, `refines`/`is-refined-by`,
  and `derives-from`/`is-derived-by` cross-references retained

**`semantic-extraction.md` → `dispatch-routing.md`**: `SE-05-002` cross-
referenced to `DR-02-002`

**`architecture.md` ↔ `code-style.md`**: `ARCH-01-001 is-derived-by CS-05-001`
/ `CS-05-001 derives-from ARCH-01-001`

**Verification**: `markdownlint-cli2` → 0 errors (453 files)

**Tests**: No code changes; docs only. Test count unchanged (1080 passed).

---

## D5-1 — Multi-Actor Architecture Review (2026-03-31)

**Task**: Confirm CA-2 follow-up complete, review current architecture for
multi-actor readiness, clarify assumptions for isolated actor/container
scenarios, and produce a refreshed architectural summary in `notes/`.

**What was done**:

- Confirmed PRIORITY-200 CA-2 follow-up (actor-first case-scoped
  action-rules endpoint) is complete and verified in IMPLEMENTATION_HISTORY.
- Reviewed current architecture: all hexagonal violations resolved, per-actor
  DataLayer isolation (ADR-0012) implemented, outbox delivery pipeline
  functional (OX-1.x), RM state tracking unified (PRIORITY-90/ADR-0013),
  CaseActor broadcast implemented (CA-1/CA-3).
- Created `notes/multi-actor-architecture.md` with:
  - CA-2 follow-up confirmation
  - Current architecture state summary (sections 2.1–2.6)
  - Six explicit assumptions for isolated actor/container scenarios (A–F)
  - Six identified gaps to address before D5-2 (G1–G6)
  - Recommended D5-2 prerequisite ordering
  - Non-goals for D5-2
- Added entry to `notes/README.md` for the new file.
- Marked D5-1 complete in `plan/IMPLEMENTATION_PLAN.md`.

**Key findings**:

- The architecture is ready for multi-actor use; remaining work is operational
  (Docker Compose, actor seeding, demo orchestration, CaseActor startup
  strategy), not architectural.
- Highest-priority D5-2 prerequisite: actor seeding CLI (G2) and
  multi-container Docker Compose config (G4).
- CaseActor instantiation strategy (G3) needs a design decision before D5-2.

**Validation**:

- `./mdlint.sh` → 0 errors (454 files)
- `uv run pytest --tb=short 2>&1 | tail -5` → `1080 passed, 5581 subtests passed`

---

## D5-1-G2 — Actor Seeding / Bootstrap CLI Command

**Status**: Complete

**Files changed**:

- `vultron/demo/seed_config.py` (new): `LocalActorConfig`, `PeerActorConfig`,
  `SeedConfig` Pydantic models with `load()`, `from_env()`, `from_file()`
  classmethods. Reads `VULTRON_ACTOR_NAME`, `VULTRON_ACTOR_TYPE`,
  `VULTRON_ACTOR_ID`, `VULTRON_SEED_CONFIG` env vars.
- `vultron/adapters/driving/fastapi/routers/actors.py`: Added `POST /actors/`
  idempotent endpoint (`create_actor`), `ActorCreateRequest` model,
  `_ACTOR_TYPE_MAP` mapping type strings to Pydantic actor classes.
- `vultron/demo/utils.py`: Added `seed_actor()` helper that calls
  `POST /actors/` via `DataLayerClient`.
- `vultron/demo/cli.py`: Added `seed` CLI sub-command wiring `SeedConfig` to
  `seed_actor()`.
- `docker/demo-entrypoint.sh`: Conditional `vultron-demo seed` call on
  container startup when `VULTRON_ACTOR_NAME` or `VULTRON_SEED_CONFIG` is
  set.
- `test/demo/test_seed_config.py` (new): 20 unit tests for `SeedConfig`,
  `LocalActorConfig`, `PeerActorConfig` (env vars, JSON file, `load()`
  priority).
- `test/demo/test_seed.py` (new): 10 tests for `seed_actor()` helper and
  `seed` CLI sub-command (via mocked `DataLayerClient`).
- `test/adapters/driving/fastapi/routers/test_actors.py`: Added
  `TestCreateActor` class (11 tests for `POST /actors/` endpoint: all actor
  types, idempotency, list visibility, retrieval by short ID).

**Key design decisions**:

- `POST /actors/` returns HTTP 201 on create, 200 on idempotent re-seed.
- Actor ID generation falls back to `make_id("actors")` when no `id` supplied.
- `GET /actors/{actor_id}` uses `find_actor_by_short_id()` for resolution,
  so full-URL actor IDs are queried via their last path segment in tests.
- `_shared_dl()` dependency wrapper prevents FastAPI path param forwarding
  into `get_datalayer(actor_id=...)` which would return an actor-scoped DL.

**Validation**:

- All 4 linters pass: `black`, `flake8`, `mypy`, `pyright` — 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1121 passed, 5581 subtests passed`

---

## D5-1-G1 and D5-1-G6 — Info Endpoint and Inbox URL Derivation Test (2026-03-31)

### D5-1-G1 — VULTRON_BASE_URL Exposure via Info Endpoint

**Task**: Add a `GET /info` endpoint returning the configured `VULTRON_BASE_URL`
and the list of actor IDs registered in the shared DataLayer.

**What was done**:

- Created `vultron/adapters/driving/fastapi/routers/info.py` with a `GET /info`
  endpoint that returns `{"base_url": BASE_URL, "actors": [list of actor IDs]}`.
  Queries all actor table types ("Actor", "Application", "Group", "Organization",
  "Person", "Service") from the shared DataLayer to build the actor list.
- Registered the new `info.router` in `vultron/adapters/driving/fastapi/routers/v2_router.py`.
- Added `test/adapters/driving/fastapi/routers/test_info.py` with 5 tests
  covering: 200 response, `base_url` and `actors` fields present, empty actors
  list when no actors seeded, and actor IDs appearing in response after seeding.
- Confirmed `/health/ready` DataLayer connectivity check (OB-05-002) was already
  implemented via `dl.ping()` — no additional work needed there.

### D5-1-G6 — Inbox URL Derivation Integration Test

**Task**: Verify that `DeliveryQueueAdapter`'s inbox URL derivation formula
(`{actor_id}/inbox/`) is consistent with the FastAPI actors router.

**What was done**:

- Created `test/adapters/driven/test_delivery_inbox_url.py` with 6 tests:
  - Unit tests verifying the derivation formula appends `/inbox/`, normalises
    trailing slashes, and preserves the actor UUID.
  - Integration test that creates an actor with a Docker-style full URI ID
    (`http://finder:7999/api/v2/actors/{uuid}`), derives the inbox URL, strips
    the `/api/v2` prefix to get the app_v2-relative path, and POSTs to the
    FastAPI actors router, asserting 202 Accepted (not 404).
  - Path shape test confirming the path relative to app_v2 is `/actors/{uuid}/inbox/`.
- **No bugs found**: derivation logic is already correct; test serves as a
  regression guard for D5-2 work.

**Validation**:

- All 4 linters pass: `black`, `flake8`, `mypy`, `pyright` — 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1132 passed, 5581 subtests passed`

---

## D5-1-G4 — Multi-Container Docker Compose Configuration (2026-03-31)

**Task**: PRIORITY-300, `plan/IMPLEMENTATION_PLAN.md` §D5-1-G4

**Summary**: Added multi-actor Docker Compose configuration and `VULTRON_DB_PATH`
env var support to the DataLayer.

**Changes**:

- `docker/docker-compose-multi-actor.yml` (new): Three actor services (`finder`
  port 7901, `vendor` port 7902, `case-actor` port 7903) plus a `demo-runner`.
  Each actor service has a unique `VULTRON_BASE_URL`, named volume at
  `/app/data/mydb.json`, healthcheck at `/api/v2/health/ready`, and
  `vultron-network` membership. `demo-runner` uses `condition: service_healthy`
  dependencies on all three actor services (DEMO-MA-02-001 through 02-003).
- `vultron/adapters/driven/datalayer_tinydb.py`: Added `import os` and
  `_DEFAULT_DB_PATH: str = os.environ.get("VULTRON_DB_PATH", "mydb.json")`
  module-level constant; changed `get_datalayer()` `db_path` parameter default
  to `_DEFAULT_DB_PATH`. Env var is read at module import time.
- `docker/Dockerfile`: Added `RUN mkdir -p /app/data` to the `api-dev` target
  to ensure the data directory exists before the volume is mounted.
- `docker/README.md`: Added "Multi-Actor Demo Setup" section with service/port
  table, env var table, startup, seeding, and volume reset instructions.
- `test/adapters/driven/test_get_datalayer.py` (new): 7 tests covering in-memory,
  file-backed, singleton, actor-scoped, reset, and env-var semantics.

**Lessons**:

- Python default argument values are bound at function definition time, not call
  time. Module-level `_DEFAULT_DB_PATH` as a default arg works correctly for
  production (env var set before process start) but requires `importlib.reload`
  or direct constructor args in tests.
- FastAPI introspects function default parameter values as query param defaults.
  Using a non-primitive sentinel (e.g., `object()`) as a default in a FastAPI
  `Depends` function causes `RequestValidationError` across all routes. Always
  use `None` or a primitive as the default in any function used with `Depends`.

**Validation**:

- All 4 linters pass: `black`, `flake8`, `mypy`, `pyright` — 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1139 passed, 5581 subtests passed`

---

## D5-1-G3 — CaseActor Instantiation Strategy (2026-03-31)

**Task**: Decide and implement the CaseActor instantiation strategy for
multi-container scenarios and document it in
`notes/multi-actor-architecture.md` §3-D.

**Chosen strategy**: Pre-seeded container identity (VultronService actor
with a deterministic `VULTRON_ACTOR_ID`) plus lazy per-case
`VultronCaseActor` records created by `CreateCaseActorNode` at case
creation time.

**Decision rationale**:

- For D5-2 (Finder + Vendor only), CaseActor co-locates in the Vendor
  container. No dedicated case-actor container is required.
- Deterministic actor IDs eliminate the need for runtime discovery: each
  container's actor URI is known before deployment.
- Peer registration via JSON seed config files keeps multi-container
  bootstrap reproducible and scriptable.

**Files changed**:

- `docker/seed-configs/seed-finder.json` (new): SeedConfig for Finder
  container with deterministic ID + Vendor and CaseActor peers.
- `docker/seed-configs/seed-vendor.json` (new): SeedConfig for Vendor
  container with deterministic ID + Finder and CaseActor peers.
- `docker/seed-configs/seed-case-actor.json` (new): SeedConfig for
  CaseActor container with deterministic ID + Finder and Vendor peers.
- `docker/docker-compose-multi-actor.yml`: Replaced `VULTRON_ACTOR_NAME`
  / `VULTRON_ACTOR_TYPE` with `VULTRON_ACTOR_ID` (deterministic) and
  `VULTRON_SEED_CONFIG` for each service. Updated header comments.
- `notes/multi-actor-architecture.md`: Rewrote §3-D with the chosen
  strategy (deterministic IDs, per-case VultronCaseActor via BT node,
  D5-2 co-location decision). Replaced §4 gap stubs with completion
  status entries for G1–G4, G6; left G5 as open.
- `test/demo/test_multi_actor_seed.py` (new): 32 tests covering schema
  validity, deterministic IDs, peer mesh consistency, and CLI seed
  integration for all three seed config files.

**Lessons**:

- The distinction between *container identity* (VultronService actor,
  created via `POST /actors/`) and *per-case CaseActor* (VultronCaseActor
  with `context=case_id`, created by `CreateCaseActorNode`) is key. The
  former is pre-seeded; the latter is created lazily at case creation.
- Deterministic actor IDs (using the Docker service name as the UUID
  suffix, e.g., `actors/finder`) make seed config JSON files static and
  human-readable, removing any need for UUID lookup during demo setup.

**Validation**:

- All 4 linters pass: `black`, `flake8`, `mypy`, `pyright` — 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1171 passed, 5581 subtests passed`

---

## 2026-03-31 — D5-1-G5 complete: two-actor multi-container demo

Implemented the remaining D5-1 prerequisite for the multi-actor demo track:
a concrete Finder + Vendor orchestration script plus CLI entry point.

**What shipped**:

- `vultron/demo/two_actor_demo.py` (new): end-to-end two-container workflow
  that seeds both containers, submits a report from Finder to Vendor,
  triggers Vendor-side validation and case engagement, sends a case invite
  back to Finder, and posts Finder's acceptance to Vendor.
- `vultron/demo/cli.py`: added `vultron-demo two-actor` with arguments for
  Finder/Vendor base URLs, deterministic actor IDs, and `--skip-health-check`.
- `docker/docker-compose-multi-actor.yml`: activated the `demo-runner`
  service with `DEMO=two-actor` and updated comments to reflect that the
  demo is now implemented rather than a placeholder.
- `test/demo/test_two_actor_demo.py` (new): 15 tests covering seeding,
  actor lookup, cross-container workflow steps, end-to-end orchestration,
  and CLI wiring.

**Key implementation details**:

- Seeding uses a two-phase approach: create each container's local actor
  first, then register cross-container peers. This avoids ordering bugs when
  deterministic peer IDs are needed before the opposite container has been
  queried.
- Cross-container delivery is simulated explicitly by posting to the target
  container's inbox with that container's `DataLayerClient`, matching the
  multi-container architecture notes without depending on outbox transport.
- Case lookup after `validate-report` is resolved via the offer's referenced
  report ID, matching the way `CreateCaseNode` persists
  `VulnerabilityCase.vulnerability_reports`.

**Validation**:

- Focused validation: `uv run pytest test/demo/test_two_actor_demo.py -x --tb=short`
  → `15 passed`
- Canonical repository validation passed:
  `uv run black vultron/ test/ && uv run flake8 vultron/ test/ && uv run mypy && uv run pyright && uv run pytest --tb=short 2>&1 | tail -5`

---

## 2026-03-31 — D5-2 complete: deterministic two-actor acceptance scenario

Completed the first multi-actor Dockerized demo scenario after the D5-1
prerequisite chain. The scenario now resets and seeds itself deterministically,
verifies authoritative Vendor-side case state, and exercises the full
Finder→Vendor report / validate / engage / invite / accept workflow.

**What shipped**:

- `vultron/demo/two_actor_demo.py`: added container reset support, optional
  CaseActor URL handling, polling for participant convergence, stronger final
  assertions, and Vendor-side local invite persistence needed for true
  multi-container accept-by-ID behavior.
- `vultron/demo/cli.py`: added `--case-actor-url` for the `two-actor`
  subcommand so the demo-runner can explicitly include the dedicated
  CaseActor service in D5-2/D5-3-era topologies.
- `vultron/core/behaviors/report/validate_tree.py`: now reuses
  `CreateInitialVendorParticipant()` so case creation during report validation
  seeds the Vendor's case participant record.
- `vultron/core/behaviors/case/nodes.py`: made
  `CreateInitialVendorParticipant` reusable from blackboard `case_id` and
  ensured it updates `actor_participant_index` as well as `case_participants`.
- `test/core/behaviors/report/test_validate_tree.py`: added regression
  coverage proving validate-report seeds the Vendor participant and case index.
- `test/demo/test_two_actor_demo.py`: expanded demo coverage for reset logic,
  CLI forwarding, and stronger end-state expectations.
- `docker/docker-compose-multi-actor.yml` and `docker/README.md`: documented
  the single-command D5-2 acceptance run and clarified environment variables /
  reset expectations.

**Key implementation details**:

- Stronger D5-2 assertions surfaced a genuine core-state defect rather than a
  demo-layer bug: validate-report created a case but skipped the initial Vendor
  participant, which in turn left `engage-case` unable to update Vendor RM
  state through the case participant model.
- The correct fix was to reuse the existing case-layer primitive rather than
  duplicate participant creation in demo code, preserving the hexagonal
  architecture and keeping demo orchestration transport-focused.
- In true multi-container mode, Accept/Reject activities sent by ID require the
  receiving container to be able to rehydrate the original Invite/Offer from
  its own DataLayer. The demo now persists the invite on the Vendor side before
  delivering it to the Finder when the two clients point at different
  containers.

**Validation**:

- Focused validation passed:
  `uv run pytest test/core/behaviors/report/test_validate_tree.py test/demo/test_two_actor_demo.py -x --tb=short`
  → `29 passed`
- Canonical repository validation passed:
  `uv run black vultron/ test/ && uv run flake8 vultron/ test/ && uv run mypy && uv run pyright && uv run pytest --tb=short 2>&1 | tail -5`
- Live Docker Compose acceptance could not complete in this environment because
  the shared Docker daemon ran out of space while creating BuildKit temp dirs
  and named volumes (`no space left on device`). The compose command and docs
  were updated for the intended run, but runtime verification remains
  environment-blocked rather than code-blocked.

---

## D5-4 — Multi-Vendor Demo with Ownership Transfer (Completed 2026-04-01)

### Summary

Implemented the multi-vendor, multi-container demo scenario (Scenario 3 from
`specs/multi-actor-demo.md`). The demo exercises the full ownership-transfer
protocol with a second vendor.

### Changes

- **`vultron/demo/multi_vendor_demo.py`** (new): 5-container scenario with
  Finder, Vendor, Coordinator, CaseActor, and Vendor2 containers. Vendor
  creates the authoritative case, proposes an embargo, then transfers case
  ownership to Coordinator (who becomes the ongoing point of contact). After
  the transfer, Coordinator invites Vendor2 into the active embargo group.
- **`docker/seed-configs/seed-vendor2.json`** (new): seed config for Vendor2
  container (deterministic ID `http://vendor2:7999/api/v2/actors/vendor2`).
- **`docker/seed-configs/seed-{finder,vendor,coordinator,case-actor}.json`**:
  updated to include Vendor2 as a peer (all configs now describe a 5-actor
  full-mesh with 4 peers each).
- **`docker/docker-compose-multi-actor.yml`**: added `vendor2` service
  (port 7905), `vendor2-data` volume, `VULTRON_VENDOR2_BASE_URL` env var,
  and `depends_on: vendor2` in `demo-runner`.
- **`vultron/demo/cli.py`**: added `multi-vendor` click command following
  the same pattern as `three-actor`.
- **`test/demo/test_multi_vendor_demo.py`** (new): 6 unit tests covering
  seed, case creation, ownership transfer assertion, and full workflow.
- **`test/demo/test_multi_actor_seed.py`**: updated to reflect 5-actor mesh
  (added `COORDINATOR_ID`, `VENDOR2_ID`; fixed peer-count assertions from
  "2 peers" to "4 peers" and seed call count from 3 to 5). Resolved
  pre-existing test failures from commit f3099bcb where coordinator was
  added to seed configs without updating the test.

### Bugs Fixed

- **`AcceptInviteToEmbargoOnCaseReceivedUseCase`** idempotency bug: the early
  return when an embargo was already active skipped participant acceptance
  recording for every actor after the first. Now case-level state changes
  (set_embargo, em_state) are skipped idempotently, but
  `participant.accepted_embargo_ids` is always updated.

### Lessons Learned

- Single-TestClient test environments share one DataLayer across all "container"
  clients. Activities posted to two different inboxes (e.g., case-actor and
  coordinator) hit the same `dl.create()` and fail on duplicate IDs. Resolve
  with the `if client_a.base_url != client_b.base_url:` guard pattern that
  `coordinator_invites_actor` already uses.
- Multi-participant embargo workflows require ALL accepting actors to update
  their `CaseParticipant.accepted_embargo_ids`. Idempotency logic must
  distinguish case-level state (which is truly idempotent once set) from
  per-participant state (which must be updated once per participant).

---

## BUG-2026040102 Fix — Circular Import in validate_tree (COMPLETE 2026-04-01)

### Issue

`test/core/behaviors/test_performance.py` failed to collect (ImportError) when
run in isolation due to a circular import chain:

```text
validate_tree → nodes → triggers._helpers (via triggers __init__)
  → triggers.report → validate_tree  ← CIRCULAR
```

The full suite sometimes passed because other modules pre-loaded `validate_tree`
first; in isolation or with unlucky ordering the partial-module error surfaced.

After fixing the import cycle, two tests in `test_performance.py` that had
previously been un-runnable also failed because:

- `CreateCaseNode` creates `VultronCase` objects, but `is_case_model()` checked
  for `record_event` which only existed on the wire-layer `VulnerabilityCase`.
- The mock DataLayer in the test did not track objects persisted via `create()`,
  so subsequent `read()` calls returned `None`.

### Root Cause

`vultron/core/behaviors/report/nodes.py` imported `update_participant_rm_state`
from `vultron.core.use_cases.triggers._helpers`.  Loading that dotted path
causes Python to first initialize `vultron.core.use_cases.triggers.__init__`,
which re-exports from `triggers.report`, which imports `create_validate_report_tree`
from `validate_tree` — before `validate_tree` had finished loading.

### Resolution

1. **Break the import cycle**: Moved `update_participant_rm_state` (and
   `resolve_case`) from `triggers/_helpers.py` to the neutral
   `vultron/core/use_cases/_helpers.py`.  `nodes.py` now imports from there,
   bypassing the `triggers` package `__init__`.
2. **Fix `is_case_model` for `VultronCase`**: Added `record_event()` to
   `VultronCase` (core model) using `VultronCaseEvent` (also core), so the
   Protocol guard returns `True` for core-created cases.
3. **Fix test mock**: Updated `mock_datalayer` in `test_performance.py` to
   store objects in an in-memory dict when `create()`/`save()` are called,
   enabling subsequent `read()` calls to find them.

### Validation

`uv run pytest test/core/behaviors/test_performance.py` — 2 passed (in isolation).
Full suite: 1199 passed, 5581 subtests passed (up from 1026; the previously
uncollectable test file now contributes 2 tests).

---

## BUG-2026040101 — Invited case participants do not reach `RM.ACCEPTED`

**Date fixed:** 2026-04-01

### Summary

Participants added via `AcceptInviteActorToCaseReceivedUseCase` could never
reach `RM.ACCEPTED` because they were created with an empty RM status history,
which resolved to `RM.START` after the DataLayer round-trip. The `engage-case`
trigger then attempted the invalid `START → ACCEPTED` transition, which the RM
state machine blocked silently.

### Root Cause

Two related issues:

1. `AcceptInviteActorToCaseReceivedUseCase` created `VultronParticipant` with
   `participant_statuses=[]`. The wire-layer `CaseParticipant.init_participant_status_if_empty`
   model validator (which fires on DataLayer read-back) seeded the participant
   at `RM.START`. The RM state machine only allows `VALID → ACCEPTED` or
   `DEFERRED → ACCEPTED`, so `START → ACCEPTED` was silently blocked.

2. `VultronParticipant` lacked `append_rm_state`, making it structurally
   incompatible with the `ParticipantModel` Protocol.

### Resolution

- Added `append_rm_state` to `VultronParticipant` in
  `vultron/core/models/participant.py`, using `is_valid_rm_transition` to
  guard transitions and appending `VultronParticipantStatus` entries.
- In `AcceptInviteActorToCaseReceivedUseCase.execute()`, after constructing
  the participant, call `append_rm_state(RM.RECEIVED, ...)` then
  `append_rm_state(RM.VALID, ...)` before persisting. Semantically, accepting
  an invitation is equivalent to having received and validated the case.
- Added regression test
  `TestInviteActorUseCases::test_accept_invite_participant_can_reach_rm_accepted`.

### Validation

1200 passed, 5581 subtests; black/flake8/mypy/pyright all clean.

---

## BUG-2026040103 — ResourceWarning: unclosed file for mydb.json (FIXED 2026-04-01)

### Summary

The full test suite emitted 10+ `ResourceWarning: unclosed file <mydb.json>`
messages at session teardown. These were printed by the Python interpreter's
`__del__` machinery (not via `warnings.warn()`), so they bypassed pytest's
`filterwarnings = ["error"]` config and did not cause test failures.

### Root Causes

1. `test/adapters/driving/fastapi/routers/test_datalayer_serialization.py` had
   an autouse `reset_datalayer` fixture that called `get_datalayer()` with the
   default file-backed `db_path` (`mydb.json`), cleared data before/after each
   test, but never called `reset_datalayer()` (the function) to close the
   TinyDB file handles. Test bodies also called `get_datalayer()` directly.

2. `test/conftest.py`'s `cleanup_test_db_files` session fixture deleted
   `mydb.json` without calling `reset_datalayer()` first, so cached
   `TinyDbDataLayer` instances held open file handles until Python shutdown.

### Resolution

- Rewrote `test_datalayer_serialization.py` fixtures to use
  `get_datalayer(db_path=None)` (in-memory) and inject the instance into
  FastAPI via `dependency_overrides`. Added proper `reset_datalayer()` teardown.
  Updated test bodies to use the `datalayer` fixture parameter.
- Added regression test `test_test_datalayer_uses_in_memory_storage` that
  asserts `MemoryStorage` is used (fails on file-backed, passes after fix).
- Updated `test/conftest.py` to call `reset_datalayer()` before deleting
  `mydb.json` in both the setup and teardown phases of `cleanup_test_db_files`.

### Validation

`uv run pytest --tb=short 2>&1 | grep -i ResourceWarning` → no output.
1201 passed, 5581 subtests; black/flake8/mypy/pyright all clean.

---

## D5-5 — Multi-Actor Integration Tests (2026-04-01)

**Task**: D5-5 — Integration tests and Docker Compose configs for each
multi-actor demo scenario.

### What was done

Created `integration_tests/demo/run_multi_actor_integration_test.sh`, a
parameterized bash script that runs any of the three multi-actor demo
scenarios (`two-actor`, `three-actor`, `multi-vendor`) as a fully
automated acceptance test. The script:

1. Accepts the scenario name as a positional argument or via the `DEMO` env
   var (default: `two-actor`).
2. Validates the scenario name against the known set.
3. Builds all Docker images using `docker compose build`.
4. Starts the full `docker-compose-multi-actor.yml` stack with
   `--abort-on-container-exit --exit-code-from demo-runner`.  The
   `demo-runner` service already declares `condition: service_healthy` on
   all actor services (DEMO-MA-02-002), so it only starts once every actor
   passes `/health/ready`.
5. Removes all volumes on exit (`down --volumes`) so each run begins from
   a clean, deterministic baseline (DEMO-MA-01-003).
6. Uses `PROJECT_NAME=vultron-it` to isolate the test stack from a running
   development stack.

Added three Makefile targets for convenience:

- `make integration-test-multi-actor`   (`DEMO=two-actor`)
- `make integration-test-three-actor`   (`DEMO=three-actor`)
- `make integration-test-multi-vendor`  (`DEMO=multi-vendor`)

Updated `integration_tests/README.md` with a full usage guide (scenario
table, isolation tips, success/failure patterns).

Updated `docker/README.md` to document D5-4 (`multi-vendor` scenario) and
add an "Automated multi-actor integration tests (D5-5)" section linking to
the new script and Makefile targets.

The existing `docker-compose-multi-actor.yml` already satisfies the Docker
Compose configuration requirements for all three scenarios (DEMO-MA-02-001
through DEMO-MA-02-003) — no separate compose files were needed.

### Validation

`uv run pytest --tb=short 2>&1 | tail -5` → 1201 passed, 5581 subtests;
all clean. The integration test script itself requires Docker and cannot be
run in the unit-test environment, but the bash script was manually verified
for correctness and the existing `run_demo_integration_test.sh` serves as
a structural reference confirming the pattern.

### Specs satisfied

- DEMO-MA-03-001: each scenario runnable via single command ✅
- DEMO-MA-03-003: reproducible runs (volumes reset on each run) ✅
- DEMO-MA-04-001: scenarios reuse the single `docker-compose-multi-actor.yml` ✅

---

## BUG-2026040104 — Multi-actor integration test port conflict (FIXED 2026-04-01)

### Summary

`integration_tests/demo/run_multi_actor_integration_test.sh` failed with an
opaque Docker networking error (`Bind for 0.0.0.0:7901 failed: port is
already allocated`) whenever any of the five hardcoded host ports (7901–7905)
were already in use on the host.

### Root Cause

`docker/docker-compose-multi-actor.yml` used hardcoded host port numbers.
The existing `PROJECT_NAME` env var avoided Docker resource naming conflicts
but did nothing for port binding conflicts.  Any concurrent dev stack,
parallel test run, or leftover container from a failed previous run could
hold one of those ports, causing a confusing Docker error.

### Resolution

1. **Configurable host ports** — Changed all five port bindings in
   `docker/docker-compose-multi-actor.yml` to `${VAR:-default}` env-var
   syntax (e.g., `"${FINDER_HOST_PORT:-7901}:7999"`).  Defaults are
   unchanged so existing `make` targets work without modification.
2. **Pre-flight port check** — Added a port-availability check to the
   integration test script.  Before starting the Docker stack the script
   probes each resolved host port with `nc -z` and fails fast with a
   human-readable error that lists conflicting ports and shows the override
   env vars needed to use different ports.
3. **Regression test** — Added `test/demo/test_multi_actor_compose.py` with
   class `TestMultiActorComposeHostPorts`.  Tests parse the YAML and assert
   that every actor service's host port uses `${VAR:-default}` syntax.
   These tests fail when ports are hardcoded and pass after the fix.
4. **Documentation** — Updated `integration_tests/README.md` with
   port-override guidance and examples.
5. **Dev dependency** — Added `types-pyyaml` for mypy stub coverage.

### Validation

`uv run pytest --tb=short 2>&1 | tail -5` → 1207 passed, 5581 subtests;
black/flake8/mypy/pyright all clean.

## D5-6-STATE: Fix Finder RM State Initialization in SubmitReportReceivedUseCase

**Task**: D5-6-STATE (PRIORITY-310 demo feedback)
**Addresses**: D5-6c from `notes/two-actor-feedback.md` — ambiguous RM state
log messages; finder participant status incorrectly initialized to `RM.RECEIVED`

### Problem

When a vendor's inbox received a submitted (`Offer`) report from a finder,
`SubmitReportReceivedUseCase` created the finder's `VultronParticipantStatus`
with `rm_state=RM.RECEIVED`. This was semantically wrong: `RM.RECEIVED` is
the **vendor's** state after receiving a new report. A finder who submits a
report has already progressed through their own RM cycle to `RM.ACCEPTED`.
The log message `"RM START → RECEIVED for report '...' (actor '...')"` was
also ambiguous about which participant's state was being described.

### Changes

1. **`vultron/core/use_cases/received/report.py`**: In
   `SubmitReportReceivedUseCase.execute()`, changed finder participant status
   initial `rm_state` from `RM.RECEIVED` to `RM.ACCEPTED`. Updated
   `_idempotent_create` label to `"ParticipantStatus (report-phase RM.ACCEPTED)
   for finder"`. Updated log to `"Finder RM: START → ACCEPTED for report '%s'
   (finder: '%s')"`.

2. **`test/core/use_cases/received/test_report.py`**: Updated existing test
   to check `RM.ACCEPTED`; added negative test, idempotency test, and log
   message verification test class `TestSubmitReportLogMessages`.

### Validation

`uv run pytest --tb=short 2>&1 | tail -5` → 1211 passed, 5581 subtests;
black/flake8/mypy/pyright all clean.

---

## D5-6-LOG — Improve process-flow logging across demo containers

**Task**: PRIORITY-310, D5-6-LOG

### Root cause fixed

`py_trees.behaviour.Behaviour.__init__` sets `self.logger = logging.Logger(name)`
where `logging` is `py_trees.logging` (a custom module, not stdlib). The custom
`py_trees.logging.Logger` class has `parent=None` and a single-arg `info(msg)`
— all BT node `self.logger.info/debug/error(...)` calls were silently dropped.

**Fix**: Override `self.logger` in `DataLayerCondition.__init__` and
`DataLayerAction.__init__` (in `vultron/core/behaviors/helpers.py`) with
`logging.getLogger(f"{__name__}.{self.__class__.__name__}")` after
`super().__init__()`.

### Changes

1. **`vultron/core/behaviors/helpers.py`**: Added
   `logger: logging.Logger  # type: ignore[assignment]` class attribute and
   `self.logger = logging.getLogger(...)  # type: ignore[assignment]` in both
   `DataLayerCondition.__init__` and `DataLayerAction.__init__`.

2. **`vultron/core/behaviors/report/nodes.py`**: Improved log messages in
   `TransitionRMtoValid` and `TransitionRMtoInvalid` to include report name
   and actor ID (e.g., `"RM → VALID for report '%s' (actor '%s')"`).

3. **`vultron/core/behaviors/case/nodes.py`**: Improved
   `CreateInitialVendorParticipant.update()` to log roles and `rm_state`
   explicitly. Fixed generator to use `str(r.value)` instead of `r.value`.

4. **`vultron/adapters/driving/fastapi/routers/actors.py`**: Changed the
   "Parsing activity from request body" log to multiline indented JSON
   (`json.dumps(body, indent=2, default=str)`).

5. **`vultron/core/use_cases/triggers/requests.py`**: Added
   `SubmitReportTriggerRequest` with `report_name`, `report_content`,
   `recipient_id` fields.

6. **`vultron/core/use_cases/triggers/report.py`**: Added
   `SvcSubmitReportUseCase` that creates a `VulnerabilityReport` and
   `RmSubmitReportActivity` (offer), stores both in the DataLayer, and queues
   the offer in the actor's outbox.

7. **`vultron/adapters/driving/fastapi/trigger_models.py`**: Added
   `SubmitReportRequest` HTTP request body model.

8. **`vultron/adapters/driving/fastapi/_trigger_adapter.py`**: Added
   `submit_report_trigger` adapter function.

9. **`vultron/adapters/driving/fastapi/routers/trigger_report.py`**: Added
   `POST /actors/{id}/trigger/submit-report` endpoint.

10. **`vultron/demo/two_actor_demo.py`**: Updated `finder_submits_report()` to
    accept optional `finder_client`; uses the new submit-report trigger when
    provided; skips inbox delivery when finder and vendor share the same
    DataLayer (single-container tests).

11. **`test/core/behaviors/test_helpers.py`**: Added 4 tests verifying the
    logger override (uses stdlib Logger, has a parent, name includes class,
    emits records via `caplog`).

12. **`test/adapters/driving/fastapi/routers/test_trigger_report.py`**: Added
    5 tests for the submit-report endpoint (202 response, DataLayer storage,
    outbox entry, 422 for missing fields, log emission via `caplog`).

### Validation

`uv run pytest --tb=short 2>&1 | tail -5` → 1220 passed, 5581 subtests;
black/flake8/mypy/pyright all clean.

---

## D5-6-STORE: Dehydrate nested AS2 objects before TinyDB storage

**Task**: PRIORITY-310 / D5-6-STORE
**Status**: Complete

### Problem

The TinyDB adapter stored transitive activities (e.g., `Offer(VulnerabilityReport)`)
with the full inline nested object serialised into the activity record. This
caused redundant storage and could cause `rehydrate()` to pick up stale inline
data instead of the live DataLayer record.

### Solution

1. **`vultron/adapters/driven/db_record.py`**: Added `_AS_OBJECT_REF_FIELDS`
   allowlist (`object_`, `target`, `origin`, `result`, `instrument`) and
   `_dehydrate_data()` function. `Record.from_obj` now calls
   `_dehydrate_data(obj.model_dump(mode="json"))`, which replaces any inline
   nested object in an allowlisted field with its ID string, provided the
   nested object has an `id_` key and its `type_` does not start with `as_`
   (domain objects only; core AS2 objects are left inline).

2. **`vultron/adapters/driving/fastapi/routers/actors.py`**: `post_actor_inbox`
   now pre-stores any inline domain-typed nested object in the DataLayer
   BEFORE storing the parent activity. This ensures `rehydrate()` can resolve
   the ID reference produced by dehydration.

3. **`vultron/core/behaviors/case/nodes.py`**: `CheckCaseAlreadyExists`
   updated to check whether the case has been FULLY INITIALISED (has at least
   one participant) rather than merely existing in the DataLayer. A pre-stored
   but uninitialised case (empty `case_participants`) now returns FAILURE,
   allowing the BT `CreateCaseFlow` to run and add participants.

4. **`vultron/demo/utils.py`**: Updated `verify_object_stored` log message.

### Tests added

- `test/adapters/driven/test_db_record.py`: 8 unit tests for `_dehydrate_data`
  and 2 integration tests for `object_to_record`.
- `test/adapters/driven/test_tinydb_backend.py`: 5 TinyDB round-trip
  integration tests.

### Lessons learned

- **`CheckCaseAlreadyExists` idempotency scope**: Idempotency checks for BT
  case creation must distinguish between a pre-stored stub (empty participants)
  and a fully-initialised case. A simple `dl.read(case_id) is not None` check
  is insufficient when the inbox endpoint pre-stores nested objects.
- **Allowlist approach for dehydration is essential**: Dehydrating ALL nested
  dicts (any dict with an `id_` key) causes broad failures — actor `inbox`/
  `outbox` fields, participant status lists, etc. Only the five canonical AS2
  transitive-activity object fields are safe candidates.
- **Lists must never be dehydrated**: List items in domain objects are either
  string lists or embedded sub-object lists; dehydrating list items breaks
  `model_validate` reconstruction.

### Validation

`uv run pytest --tb=short 2>&1 | tail -5` → 1236 passed, 5581 subtests;
black/flake8/mypy/pyright all clean.

---

## D5-6-WORKFLOW — Automate complete case creation from validate-report

**Date**: 2026-04-06
**Task**: PRIORITY-310 D5-6-WORKFLOW

### Changes

- `vultron/core/behaviors/case/nodes.py`:
  - Added `InitializeDefaultEmbargoNode`: creates a default embargo event
    (duration from actor's EmbargoPolicy, falling back to 90 days) and
    attaches it to the newly created case.
  - Added `CreateFinderParticipantNode`: reads the Offer to find the finder's
    actor ID, reuses the report-phase RM.ACCEPTED status, creates a
    `VultronParticipant` with FINDER+REPORTER roles, attaches it to the case,
    records a `"participant_added"` case event, and emits an Add notification.
  - Updated `CreateInitialVendorParticipant`: added `advance_to_accepted`
    parameter (default `False`); when `True`, advances vendor RM VALID →
    ACCEPTED immediately after participant creation (validate-report tree sets
    this; create-case tree leaves it `False` per ADR-0013).
  - Fixed `CreateCaseActivity`: replaced `dl.read(offer_id)` with
    `dl.by_type("Offer").get(offer_id)` because `VultronOffer` is not
    registered in the AS2 vocabulary and cannot be reconstructed by `read()`.

- `vultron/core/behaviors/report/validate_tree.py`:
  - Expanded `ValidationActions` sequence from 5 to 7 nodes: added
    `InitializeDefaultEmbargoNode` (after `CreateCaseNode`) and
    `CreateFinderParticipantNode` (after `CreateInitialVendorParticipant`).
  - Passes `advance_to_accepted=True` to `CreateInitialVendorParticipant`.

- `vultron/demo/two_actor_demo.py`:
  - Removed `vendor_engages_case()` function (now handled by BT).
  - Removed `vendor_adds_finder_as_participant()` function (now handled by BT).
  - Updated `run_two_actor_demo()`: removed steps 3-engage and 4-add-finder;
    added `wait_for_case_participants` right after validate-report; renumbered
    steps 5→4, 6→5; updated docstring.
  - Removed unused imports (`AddParticipantToCaseActivity`,
    `CreateParticipantActivity`, `FinderReporterParticipant`).

- `test/core/behaviors/report/test_validate_tree.py`:
  - Added `finder_actor_id` and `finder_actor` fixtures; updated `offer`
    fixture to use finder as actor.
  - Updated node count assert 5→7; updated vendor RM check VALID→ACCEPTED.
  - Added 3 new tests: finder participant created, default embargo initialized,
    vendor RM advanced to ACCEPTED.

- `test/demo/test_two_actor_demo.py`:
  - Removed `TestVendorEngagesCase` and `TestVendorAddsFinder` test classes.
  - Updated `_setup_case_with_two_participants` to remove the old manual
    engage/add-finder calls; now relies on BT + `wait_for_case_participants`.

- `test/core/behaviors/test_performance.py`:
  - Added `by_type` and `record_outbox_item` mocks to `mock_datalayer`
    fixture.

### Validation

`uv run pytest --tb=short 2>&1 | tail -5` → 1237 passed, 5581 subtests;
black/flake8/mypy/pyright all clean.

---

## Phase PRIORITY-310 — D5-6-LOG, D5-6-STATE, D5-6-STORE, D5-6-WORKFLOW (COMPLETE 2026-04-06)

These four tasks addressed reviewer feedback D5-6a–h from
`notes/two-actor-feedback.md`. All four were completed and validated
(black/flake8/mypy/pyright/pytest clean) as of 2026-04-06.

### D5-6-LOG — Improve process-flow logging across demo containers

Improved INFO-level logging so container logs tell a coherent process-flow
story (D5-6a, b, e, f, g):

- Added INFO log entries to finder actor for outgoing activity creation (report
  creation, OfferReport submission) so finder actions visible in combined log.
- Formatted "Parsing activity from request body" entries as multiline indented
  JSON.
- Added INFO-level logs throughout vendor BT sequences: RM state transitions,
  case creation steps, embargo initialization.
- Added INFO-level logs for participant record actions: creation, status record
  creation (with role and status values), and attachment to case.
- Verified combined container logs allow following full process flow.

### D5-6-STATE — Clarify RM state log messages; initialize finder participant

Fixed RM state transition log clarity and finder initial state (D5-6c):

- Updated RM state transition logs to explicitly identify which actor's state
  is changing (e.g., "Vendor RM: START → RECEIVED" vs "Finder RM: ACCEPTED").
- When vendor receives submitted report, creates CaseParticipant status record
  for finder initialized to RM.ACCEPTED (finder must be at RM.ACCEPTED to
  submit).

### D5-6-STORE — Verify datalayer reference storage for nested objects

Investigated and confirmed datalayer stores nested objects by reference (D5-6d):

- Confirmed TinyDB adapter stores activities with nested objects serialized
  inline at save time, but the use-case code constructs activities with ID
  references where appropriate.
- Updated demo-runner log messages to clarify rehydrated views vs stored
  references.
- Added datalayer tests confirming transitive activities use ID references.

### D5-6-WORKFLOW — Automate complete case creation from validate-report

Refactored validate-report BT to execute complete case creation as single
automated sequence (D5-6h). The 7-node ValidationActions sequence:

1. TransitionRMtoValid — vendor RM → VALID
2. CreateCaseNode — creates VulnerabilityCase with report reference
3. InitializeDefaultEmbargoNode — creates embargo + AnnounceEmbargo activity
4. CreateInitialVendorParticipant — vendor participant, RM → ACCEPTED
5. CreateFinderParticipantNode — finder participant + Add notification
6. CreateCaseActivity — generates CreateCaseActivity for notification
7. UpdateActorOutbox — queues activities to vendor's outbox

Removed manual engage-case and add-finder-participant steps from two-actor
demo. Updated tests to verify full automated workflow.

---

## D5-6-DUP — Fix duplicate VulnerabilityReport WARNING (2026-04-07)

**Root cause**: The inbox endpoint (`actors.py`) pre-stores any inline nested
object (e.g. the `VulnerabilityReport` inside an `Offer`) before dispatching.
When `SubmitReportReceivedUseCase` (or `CreateReportReceivedUseCase`) then
calls `dl.create()` on the same report, a `ValueError` is raised and was
previously logged at `WARNING`. This is a false-positive — the duplicate is an
expected idempotency condition, not a real error.

**Fix**: Changed the log level from `WARNING` to `DEBUG` in both
`SubmitReportReceivedUseCase` and `CreateReportReceivedUseCase`, with
explanatory comments. This matches the pattern already used for the activity
duplicate handling in `SubmitReportReceivedUseCase` (lines 116-123 before this
change). Added `TestDuplicateReportHandling` class with two tests confirming
no WARNING is emitted when the report has been pre-stored by the inbox
endpoint.

**Files changed**:

- `vultron/core/use_cases/received/report.py`
- `test/core/use_cases/received/test_report.py`

---

## D5-6-TRIGDELIV — Fix trigger endpoints to deliver outbox activities (2026-04-07)

**Root cause**: All nine trigger endpoints (`trigger_report.py`,
`trigger_case.py`, `trigger_embargo.py`) executed the use case and returned
202, but never scheduled `outbox_handler` as a `BackgroundTask`. Activities
queued by the use cases via `add_activity_to_outbox` → `record_outbox_item`
remained in the delivery queue indefinitely.

**Fix**: Added `BackgroundTasks` as a dependency to all nine trigger endpoint
functions and scheduled `outbox_handler(actor_id, get_datalayer(actor_id), dl)`
as a background task after each successful use-case execution. The actor-scoped
DataLayer (`get_datalayer(actor_id)`) manages the outbox queue; the shared DL
(`dl` from `Depends(_actor_dl)`) is passed as `shared_dl` for activity object
lookup. This matches the pattern used by `post_actor_outbox` in `actors.py`.

**Tests added**: `TestTriggerReportOutboxScheduling` (3 tests),
`TestTriggerCaseOutboxScheduling` (2 tests),
`TestTriggerEmbargoOutboxScheduling` (3 tests) — each patches `outbox_handler`
with `AsyncMock` and `get_datalayer` with `MagicMock`, then verifies the mock
was called with the correct `actor_id` and DataLayer after a successful trigger
request.

**Files changed**:

- `vultron/adapters/driving/fastapi/routers/trigger_report.py`
- `vultron/adapters/driving/fastapi/routers/trigger_case.py`
- `vultron/adapters/driving/fastapi/routers/trigger_embargo.py`
- `test/adapters/driving/fastapi/routers/test_trigger_report.py`
- `test/adapters/driving/fastapi/routers/test_trigger_case.py`
- `test/adapters/driving/fastapi/routers/test_trigger_embargo.py`

---

## D5-6-LOGCTX — Improve outbox activity log messages with human-readable context (2026-04-07)

**Task**: D5-6-LOGCTX (PRIORITY-310)

**Summary**: Improved all outbox activity queuing and delivery log messages to include activity type, object/case context, and reason for queuing. Before this change, logs showed only bare URNs (e.g., `"Queued Add activity 'urn:uuid:...'"`) with no indication of what the activity contained or why it was queued.

**Changes made**:

- `outbox_handler.handle_outbox_item`: delivery log now shows activity type, object reference, recipient count, and recipient URL list (e.g., `"Delivered Announce activity '...' (object: urn:...) to 1 recipient(s) [https://example.org/actors/finder] for actor '...'"`)
- `InitializeDefaultEmbargoNode`: queue log now shows `"Queued Announce(embargo '...', case '...', duration N days) activity '...' to actor '...' outbox (default embargo notification)"`
- `CreateFinderParticipantNode`: queue log now shows `"Queued Add(CaseParticipant '...' for actor '...' to case '...') activity '...' to actor '...' outbox (finder participant notification)"`
- `UpdateActorOutbox` (both `case/nodes.py` and `report/nodes.py`): now registers `case_id` READ access and logs `"Queued Create(Case '...') activity '...' to actor '...' outbox (case creation notification)"`
- Added `caplog` tests in 4 test files verifying activity type and context appear in improved log messages

**Files changed**:

- `vultron/adapters/driving/fastapi/outbox_handler.py`
- `vultron/core/behaviors/case/nodes.py`
- `vultron/core/behaviors/report/nodes.py`
- `test/adapters/driving/fastapi/test_outbox.py`
- `test/core/behaviors/case/test_create_tree.py`
- `test/core/behaviors/report/test_nodes.py`
- `test/core/behaviors/report/test_validate_tree.py`

---

## D5-6-DEMOAUDIT — Audit and refactor all demos for protocol compliance (2026-04-07)

**Task**: D5-6-DEMOAUDIT (PRIORITY-310)

**Summary**: Audited multi-actor demo scripts against the protocol documentation
and applied targeted fixes to ensure demos demonstrate genuine protocol-driven
behavior rather than puppeteered workflows.

### Changes made

1. **CreateCaseActivity `to` field and full case embedding**
   (`vultron/core/behaviors/report/nodes.py`): The `CreateCaseActivity` node in
   the validate-report BT now derives addressees from `offer.actor`,
   `report.attributedTo`, and `offer.to` (excluding the sending actor). The full
   `VulnerabilityCase` is embedded as `object_` so receiving actors can store
   the case immediately from the activity payload without a separate fetch.

2. **CreateFinderParticipantNode `to` field**
   (`vultron/core/behaviors/case/nodes.py`): The `Add(CaseParticipant)`
   notification activity now sets `to=[finder_actor_id]` so the finder's inbox
   receives the participant-added notification.

3. **outbox_handler case object expansion**
   (`vultron/adapters/driving/fastapi/outbox_handler.py`): `handle_outbox_item`
   now expands `Create` activity `object_` from the DataLayer before delivery,
   so recipients receive the full domain object (e.g., `VulnerabilityCase`)
   rather than just an ID string reference.

4. **Finder case verification** (`vultron/demo/two_actor_demo.py`): Added
   `wait_for_finder_case()` polling helper and a `demo_check` verification block
   to confirm the finder received the case via cross-container protocol message
   delivery (not manual injection). The verification polls the finder's
   `/actors/{id}/objects/` endpoint until the case appears or a timeout elapses.

5. **Test updates**: Assertions in `test_nodes.py` and `test_validate_tree.py`
   updated to use `by_type()` raw data dicts for `Create`/`Add` activities
   (bypasses vocabulary deserialization for domain activity types that are not
   yet in the standard registry).

6. **Remaining gaps documented**: The `InitializeDefaultEmbargoNode` still
   creates `Announce(embargo)` with no `to` field (D5-6-EMBARGORCP remains
   open); `EmitCreateCaseActivity` in `case/nodes.py` (create-case BT) still
   lacks a `to` field (D5-6-CASEPROP partially open); auto-engagement after
   invitation acceptance is not yet implemented (D5-6-AUTOENG open); note
   broadcast to participants is not yet implemented (D5-6-NOTECAST open).

### Files changed

- `vultron/core/behaviors/report/nodes.py`
- `vultron/core/behaviors/case/nodes.py`
- `vultron/adapters/driving/fastapi/outbox_handler.py`
- `vultron/demo/two_actor_demo.py`
- `test/core/behaviors/report/test_nodes.py`
- `test/core/behaviors/report/test_validate_tree.py`

---

## D5-6-AUTOENG — Auto-engage after invitation acceptance (2026-04-08)

**Task**: D5-6-AUTOENG (PRIORITY-310)

**Summary**: Invitation acceptance now completes the RM engagement step
automatically, so invited actors reach RM.ACCEPTED and emit an engage activity
without a separate demo-runner trigger.

### Changes made

1. **Auto-engage in receive-side use case**
   (`vultron/core/use_cases/received/actor.py`):
   `AcceptInviteActorToCaseReceivedUseCase` now invokes
   `SvcEngageCaseUseCase` immediately after creating the participant record and
   pre-seeding RECEIVED/VALID RM states. This advances the invited actor to
   RM.ACCEPTED and queues an `RmEngageCaseActivity` in the actor outbox.

2. **Receive-side regression coverage**
   (`test/core/use_cases/received/test_actor.py`): Updated invitation-acceptance
   tests to persist the invited actor in the DataLayer, assert direct
   RM.ACCEPTED auto-engagement, and verify that a Join/engage activity is
   queued in the invited actor's outbox.

3. **Demo workflow cleanup**
   (`vultron/demo/three_actor_demo.py`,
   `vultron/demo/multi_vendor_demo.py`): Removed the manual `engage-case`
   trigger calls that followed invite acceptance. The demos now rely on the
   protocol flow triggered by `Accept(Invite(...))`.

### Files changed

- `vultron/core/use_cases/received/actor.py`
- `test/core/use_cases/received/test_actor.py`
- `vultron/demo/three_actor_demo.py`
- `vultron/demo/multi_vendor_demo.py`

### Validation

- `uv run black vultron/ test/`
- `uv run flake8 vultron/ test/`
- `uv run mypy`
- `uv run pyright`
- `uv run pytest --tb=short 2>&1 | tail -5` → `1262 passed, 5581 subtests passed in 34.21s`

---

## D5-6-NOTECAST and D5-6-CASEPROP — Note broadcast + case propagation fix

**Completed**: 2026-04-10
**Tasks**: D5-6-NOTECAST, D5-6-CASEPROP

### D5-6-NOTECAST — Broadcast notes to case participants

`AddNoteToCaseReceivedUseCase` now broadcasts an `AddNoteToCaseActivity` to
all case participants (excluding the note author) after adding a note to a
case, satisfying CM-06-005. The CaseActor is located by `by_type("Service")`
filtered on `context == case_id`; recipients are derived from
`VulnerabilityCase.actor_participant_index`. The broadcast is created,
appended to the CaseActor's `outbox.items`, and queued via
`record_outbox_item` for delivery by `outbox_handler`.

The manual note-forwarding block in `vultron/demo/two_actor_demo.py`
(`vendor_replies_to_question`) has been removed — the CaseActor broadcast
now handles distribution automatically.

Three new tests cover: broadcast created, author excluded, graceful skip when
no CaseActor.

### D5-6-CASEPROP — EmitCreateCaseActivity now embeds full case + `to` field

`EmitCreateCaseActivity.update()` in `vultron/core/behaviors/case/nodes.py`
now reads the full `VulnerabilityCase` from the DataLayer, embeds it as
`object_`, and derives `to` from `actor_participant_index` (excluding the
actor itself). This aligns it with the reference `CreateCaseActivity` in
`vultron/core/behaviors/report/nodes.py`.

### Validation

- `uv run black vultron/ test/` → 463 files unchanged
- `uv run flake8 vultron/ test/` → no errors
- `uv run mypy` → no issues (466 source files)
- `uv run pyright` → 0 errors, 0 warnings
- `uv run pytest --tb=short 2>&1 | tail -5` → `1265 passed, 5581 subtests passed in 34.16s`

---

## D5-6-EMBARGORCP — Remove Redundant Embargo Announce Activity (COMPLETE 2026-04-11)

### What was done

Removed the standalone `Announce(embargo)` activity from
`InitializeDefaultEmbargoNode.update()` in
`vultron/core/behaviors/case/nodes.py`. The node was creating a generic
`VultronActivity(type_="Announce")` with no `to` field and queuing it to the
outbox — an unaddressed broadcast. Per `notes/protocol-event-cascades.md`
Option 2, this is redundant: the finder already receives embargo information
via `VulnerabilityCase.active_embargo` embedded in the `Create(Case)`
activity sent by `CreateCaseActivity` / `EmitCreateCaseActivity`.

Updated docstring to reflect that embargo info flows via `Create(Case)`.
Replaced the old `test_validate_report_tree_logs_announce_type_for_embargo`
test with two new tests verifying the correct behavior:

- `test_validate_report_tree_case_has_active_embargo`
- `test_validate_report_tree_create_case_activity_embeds_embargo`

### Files changed

- `vultron/core/behaviors/case/nodes.py` — removed ~25 lines from
  `InitializeDefaultEmbargoNode.update()`; updated docstring
- `test/core/behaviors/report/test_validate_tree.py` — replaced one test
  with two new tests

### Validation

- `uv run black vultron/ test/` → files reformatted; clean
- `uv run flake8 vultron/ test/` → no errors
- `uv run mypy` → no issues
- `uv run pyright` → 0 errors, 0 warnings
- `uv run pytest --tb=short 2>&1 | tail -5` → `1267 passed, 5581 subtests passed in 32.59s`

---

## IDEA-260408-01-1 — Add DataLayer report→case lookup (2026-04-08)

**Task**: Add `find_case_by_report_id(report_id: str)` to the `DataLayer`
Protocol and `TinyDbDataLayer` adapter so that report-centric use cases can
dereference a report ID to its associated `VulnerabilityCase`.

### What was done

- Added `find_case_by_report_id(report_id: str) -> PersistableModel | None`
  to the `DataLayer` Protocol in `vultron/core/ports/datalayer.py`. Return
  type is `PersistableModel | None` (not `VulnerabilityCase | None`) to
  preserve hexagonal architecture — core ports cannot import wire-layer types.
- Implemented `find_case_by_report_id` in `TinyDbDataLayer`
  (`vultron/adapters/driven/datalayer_tinydb.py`). The method searches the
  `VulnerabilityCase` table and checks each record's
  `data_["vulnerability_reports"]` list for the given `report_id` — handling
  both string ID entries and inline serialised object dicts (with `id_` key).
- Added 5 unit tests to `test/adapters/driven/test_tinydb_backend.py`:
  - report stored as string ID → case returned
  - report stored as inline object → case returned
  - report not linked to any case → None returned
  - no VulnerabilityCase table exists → None returned
  - report ID not linked (other cases exist) → None returned

### Files changed

- `vultron/core/ports/datalayer.py` — added `find_case_by_report_id` stub
- `vultron/adapters/driven/datalayer_tinydb.py` — implemented method
- `test/adapters/driven/test_tinydb_backend.py` — 5 new unit tests

### Validation

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1272 passed, 5581 subtests passed in 31.35s`

---

## EMBARGO-DUR-1 — EmbargoPolicy ISO 8601 Duration Fields (2026-04-09)

**Task**: EMBARGO-DUR-1 (Priority 310)

**Summary**: Updated `EmbargoPolicy` Pydantic model to use ISO 8601 duration
strings (e.g. `"P90D"`) at the wire layer, with `datetime.timedelta` as the
internal representation, per `specs/embargo-policy.md` EP-01-002/003 and
`specs/duration.md` DUR-01-001, DUR-04-001, DUR-05-001, DUR-05-002.

### What was done

- **`vultron/wire/as2/vocab/objects/embargo_policy.py`**: Replaced integer
  `preferred_duration_days`, `minimum_duration_days`, `maximum_duration_days`
  fields with `preferred_duration`, `minimum_duration`, `maximum_duration`
  typed as `timedelta` / `timedelta | None`. Added `_parse_duration()` helper
  using `isodate` that rejects calendar units (years, months, weeks per
  DUR-04-001) and malformed strings (DUR-04-002). A `field_validator` and
  `field_serializer` pair handles ISO 8601 ↔ `timedelta` conversion.
- **`vultron/core/behaviors/case/nodes.py`**: `InitializeDefaultEmbargoNode`
  now reads `preferred_duration` (ISO 8601 string) from the stored policy
  dict and parses it via `isodate`. Falls back to 90-day default if the field
  is absent, unparseable, or uses calendar units.
- **`test/wire/as2/vocab/test_embargo_policy.py`**: Full rewrite to use ISO
  8601 strings and `timedelta` comparisons. Added 20 new tests covering
  DUR-04-001 (reject Y/M/W), DUR-04-002 (reject malformed), DUR-04-003
  (reject empty), DUR-05-001/002 (timedelta internal, ISO 8601 JSON), and
  round-trip serialization via `object_to_record` and `TinyDbDataLayer`.
- **`test/wire/as2/vocab/test_vultron_actor.py`**: Updated `_make_policy()`
  to use `timedelta()` values.

### Validation

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1282 passed, 5581 subtests passed in 30.94s`

---

## IDEA-260408-01-2 — New BT: `receive_report_case_tree` (COMPLETE 2026-04-08)

### Summary

Created `vultron/core/behaviors/case/receive_report_case_tree.py` — a new
Behavior Tree that creates a `VulnerabilityCase` (and all its required initial
state) at the RM.RECEIVED stage, per ADR-0015.

### Changes

- **`vultron/core/behaviors/case/nodes.py`**:
  - Added `CheckCaseExistsForReport` condition node — uses
    `find_case_by_report_id` to provide idempotency guard for the new tree.
  - Modified `CreateInitialVendorParticipant.__init__` to accept
    `initial_rm_state: RM = RM.VALID` (backward-compatible default).
    `update()` now uses `self.initial_rm_state` for deterministic status-ID
    lookup and fallback creation; if the datalayer already holds a record with
    the deterministic ID it reuses that ID rather than creating a duplicate.

- **`vultron/core/behaviors/case/receive_report_case_tree.py`** (NEW):
  - `create_receive_report_case_tree(report_id, offer_id)` returns a
    `Selector("ReceiveReportCaseBT")` with two children:
    1. `CheckCaseExistsForReport` — succeeds (early exit) when the case
       already exists, providing idempotency.
    2. `Sequence("ReceiveReportCaseFlow")` — six-node flow:
       `CreateCaseNode` → `CreateInitialVendorParticipant(RM.RECEIVED)` →
       `CreateFinderParticipantNode` → `InitializeDefaultEmbargoNode` →
       `CreateCaseActivity` → `UpdateActorOutbox`.

- **`test/core/behaviors/case/test_receive_report_case_tree.py`** (NEW):
  14 tests covering tree structure, full execution, vendor/finder participant
  RM states, embargo creation, outbox queuing, idempotency, and status reuse.

### Validation

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1296 passed, 5581 subtests passed in 31.43s`

---

## IDEA-260408-01-3 + IDEA-260408-01-4: ADR-0015 Case Creation at RM.RECEIVED (completed)

### Summary

Implemented ADR-0015: moved case creation from RM.VALID (validate_report BT) to
RM.RECEIVED (SubmitReportReceivedUseCase via BTBridge). Slimmed validate_report
BT by removing 6 case-creation nodes; added `EnsureEmbargoExists` condition.

### Changes

- **`vultron/core/behaviors/report/nodes.py`**:
  - Added `EnsureEmbargoExists` condition node (DataLayerCondition subclass):
    calls `find_case_by_report_id` and checks `case.active_embargo is not None`.
  - Updated `TransitionRMtoValid.update()` to also call
    `update_participant_rm_state` (guarded by `is_case_model`) so that
    CaseParticipant.participant_statuses is updated to RM.VALID; this enables
    the engage-case trigger to advance to RM.ACCEPTED without a blocked
    RECEIVED → ACCEPTED transition.

- **`vultron/core/behaviors/report/validate_tree.py`**:
  - `ValidationActions` now has 2 children: `TransitionRMtoValid` +
    `EnsureEmbargoExists` (removed 6 case-creation nodes per ADR-0015).

- **`vultron/core/use_cases/received/report.py`**:
  - `SubmitReportReceivedUseCase.execute()`: gets `vendor_actor_id =
    request.target_id`; calls BTBridge + `create_receive_report_case_tree`.

- **`vultron/core/behaviors/case/nodes.py`**:
  - `CreateFinderParticipantNode` fallback log: WARNING → INFO.

- **`vultron/demo/receive_report_demo.py`**:
  - `make_submit_offer`: added `target=vendor.id_` to offer.

- **`vultron/demo/two_actor_demo.py`**:
  - In-memory offer: added `target=vendor.id_`.
  - Removed pre-ADR-0012 guard that skipped inbox delivery in
    single-container setups; always deliver offer to vendor inbox.
  - Added `engage-case` trigger step after `vendor_validates_report`.
  - Updated comments: case is now created at RM.RECEIVED, not RM.VALID.

- **`vultron/core/use_cases/triggers/report.py`**:
  - `submit_report_trigger`: added `target=request.recipient_id` to offer.

- **`vultron/adapters/driving/fastapi/routers/actors.py`**:
  - Inbox endpoint: wrapped `dl.create(object_to_record(activity))` in
    try/except for idempotency (trigger may have already stored the offer).

- **`test/adapters/driving/fastapi/routers/test_trigger_report.py`**:
  - Fixed `offer.object_id` → `offer.object_`; removed redundant local imports.

- **`test/adapters/driving/fastapi/test_trigger_services.py`**:
  - Fixed `offer.object_id` → `offer.object_`.

- **`test/core/behaviors/report/test_validate_tree.py`**:
  - Added `case` fixture; updated structure tests; removed 10 stale tests;
    added 3 new tests.

- **`test/core/use_cases/received/test_report.py`**:
  - Added `TestSubmitReportCreatesCase` (5 new tests); updated
    `_make_submit_event`; fixed duplicate handling tests.

- **`test/core/use_cases/received/conftest.py`** (NEW):
  - Imports `VulnerabilityCase` for vocabulary registration side-effect.

### Validation

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1290 passed, 5581 subtests passed in 44.56s`

---

## IDEA-260408-01-5 and IDEA-260408-01-6 — Dereference Pattern + Remove Standalone VultronParticipantStatus

**Completed**: 2026-04-08
**Commit**: `d5 f2ff3ebe`

### Summary

Implemented the dereference pattern for report-centric use cases and removed
standalone `VultronParticipantStatus` creation from `CreateReport` and
`AckReport` use cases.

### Changes

**`vultron/core/use_cases/received/case.py`** — added three internal case-level
helpers not in `USE_CASE_MAP`:

- `InvalidateCaseUseCase(dl, case_id, actor_id)` — transitions participant to
  `RM.INVALID`
- `CloseCaseUseCase(dl, case_id, actor_id)` — transitions participant to
  `RM.CLOSED`
- `ValidateCaseUseCase(dl, case_id, actor_id)` — runs `validate_report_tree` BT

**`vultron/core/use_cases/received/report.py`** — updated three use cases:

- `InvalidateReportReceivedUseCase`: dereferences `report_id → case_id` via
  `find_case_by_report_id`, then delegates to `InvalidateCaseUseCase`
- `CloseReportReceivedUseCase`: same pattern, delegates to `CloseCaseUseCase`
- `ValidateReportReceivedUseCase`: same pattern, delegates to `ValidateCaseUseCase`
- `CreateReportReceivedUseCase`: removed standalone `VultronParticipantStatus`
  creation
- `AckReportReceivedUseCase`: removed standalone `VultronParticipantStatus`
  creation

**`test/core/use_cases/received/test_report.py`** — updated tests:

- Replaced `TestReportReceiptPersistsParticipantStatus` with
  `TestCreateReportNoStandaloneParticipantStatus`
- Added `TestCaseLevelUseCases`, `TestDereferencePatternInReportUseCases`,
  `TestAckReportNoStandaloneStatus`
- Used `cast()` to narrow `dl.read()` return types for pyright
- Fixed close tests: use `RM.INVALID` as initial state (`RECEIVED → CLOSED`
  is not a valid RM transition; valid sources are `INVALID`, `ACCEPTED`,
  `DEFERRED`)

### Validation

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1299 passed, 5581 subtests passed in 42.49s`

---

## IDEA-260408-01-7 — Update tests for ADR-0015 case-creation move

**Task**: Update or remove existing tests that assert case creation happens
during `ValidateReport` BT execution. Add integration test verifying the
full flow: `Offer(Report)` receipt creates case → `ValidateReport` validates
without re-creating case → case is in RM.VALID state with correct
participants.

**Completed**: IDEA-260408-01-7

### Changes

- `test/core/use_cases/received/test_report.py`: Added `TestFullReportFlow`
  class with 5 integration tests:
  - `test_full_flow_case_created_at_received` — case exists after
    SubmitReport, before ValidateReport
  - `test_full_flow_validate_does_not_recreate_case` — only one case in DL
    after full flow
  - `test_full_flow_vendor_in_rm_valid_after_validate` — vendor's RM state
    is VALID after ValidateReport
  - `test_full_flow_finder_remains_rm_accepted` — finder's RM state stays
    ACCEPTED (unchanged by ValidateReport)
  - `test_full_flow_produces_correct_final_state` — combined assertion on
    case count, vendor RM.VALID, finder RM.ACCEPTED
- Confirmed `test/core/behaviors/report/test_validate_tree.py` already
  correctly reflects ADR-0015 (no case creation in validate-report BT).

### Validation

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1304 passed, 5581 subtests passed in 41.38s`

---

## BUG-2026040901 — Outbox Delivery Silent Drop in Trigger Routes (FIXED)

**Root Cause**: Trigger routes (`trigger_case.py`, `trigger_report.py`,
`trigger_embargo.py`) received `actor_id` as a short UUID from the URL path.
Use-case helpers called `resolve_actor()` to get the canonical full URI
(`actor.id_`), then wrote outbox items via `record_outbox_item(full_uri, ...)`,
creating a TinyDB table named `{full_uri}_outbox`. However, `outbox_handler`
was scheduled with `get_datalayer(short_uuid)`, creating a DataLayer scoped
to `{short_uuid}_outbox` — a completely different table. Items written to the
full-URI table were never found, silently dropping all outbox delivery.

**Fix**: Added a `_canonical_actor_dl` FastAPI dependency to each trigger router
that resolves `actor_id` to the actor's canonical URI via the shared DataLayer
(`dl.read(actor_id) or dl.find_actor_by_short_id(actor_id)`), then returns
`get_datalayer(canonical_id)`. Routes now accept `actor_dl: DataLayer =
Depends(_canonical_actor_dl)` and pass it directly to `outbox_handler`,
ensuring the handler reads from the same `{canonical_uri}_outbox` table that
the use case wrote to.

**Files changed**:

- `vultron/adapters/driving/fastapi/routers/trigger_case.py`
- `vultron/adapters/driving/fastapi/routers/trigger_report.py`
- `vultron/adapters/driving/fastapi/routers/trigger_embargo.py`
- `test/adapters/driving/fastapi/routers/test_trigger_case.py` (regression test)
- `test/adapters/driven/test_datalayer_isolation.py` (updated contract tests)

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1307 passed, 5581 subtests passed in 43.97s`

## BUG-2026040902: Fix Pydantic serialization alias bugs in domain models

**Bug**: Two-actor Docker integration test fails because the finder
never receives the `Create(VulnerabilityCase)` activity from the
vendor. Root cause: missing Pydantic v2 field aliases in domain models
break HTTP outbox delivery serialization.

**Root cause (two bugs)**:

1. `VultronBase.id_` had `Field(default_factory=_new_urn)` with no
   `validation_alias` or `serialization_alias`. This caused
   `model_dump(by_alias=True)` to emit `"id_"` instead of `"id"`, and
   `model_validate({"id": "..."})` to generate a new UUID instead of
   preserving the original.

2. Ten domain model subclasses overrode `type_` with bare
   `Literal[...] = ...` annotations, losing the parent's
   `Field(validation_alias="type", serialization_alias="type")`
   metadata. Affected: `VultronOffer`, `VultronAccept`,
   `VultronCreateCaseActivity`, `VultronCase`, `VultronReport`,
   `VultronCaseActor`, `VultronParticipantStatus`,
   `VultronParticipant`, `VultronCaseStatus`, `VultronEmbargoEvent`,
   `VultronNote`.

**Fix**: Added proper `validation_alias` and `serialization_alias` to
`VultronBase.id_` and all `type_` overrides in domain model
subclasses.

**Tests**: 14 regression tests in
`test/core/models/test_serialization_roundtrip.py` covering id_
alias serialization/deserialization/round-trip, subclass type_ alias
fidelity, and cross-model round-trip (simulating outbox delivery).

**Files changed**:

- `vultron/core/models/base.py`
- `vultron/core/models/activity.py`
- `vultron/core/models/case.py`
- `vultron/core/models/report.py`
- `vultron/core/models/case_actor.py`
- `vultron/core/models/participant_status.py`
- `vultron/core/models/participant.py`
- `vultron/core/models/case_status.py`
- `vultron/core/models/embargo_event.py`
- `vultron/core/models/note.py`
- `test/core/models/test_serialization_roundtrip.py` (new)
- `plan/BUGS.md` (updated status)

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1321 passed, 5581 subtests passed in 45.34s`

---

## D5-7-LOGCLEAN-1 + D5-7-MSGORDER-1 (2026-04-14)

### D5-7-LOGCLEAN-1 — Replace verbose Pydantic repr in outbox delivery log

Added `_format_object(obj)` helper to `outbox_handler.py` that returns
`"<ClassName> <id>"` for domain objects, passes strings through unchanged, and
handles `None`. Replaced `activity_object` in the INFO delivery log with
`_format_object(activity_object)`, eliminating hundreds of characters of
Pydantic field-repr noise.

**Files changed**:

- `vultron/adapters/driving/fastapi/outbox_handler.py` — added `_format_object`,
  updated delivery log
- `test/adapters/driving/fastapi/test_outbox.py` — added 5 tests covering
  `_format_object` variants and verifying no Pydantic repr in delivery log

### D5-7-MSGORDER-1 — Create(Case) must precede Add(CaseParticipant) in outbox

Reordered BT nodes in `receive_report_case_tree.py` so `CreateCaseActivity` +
`UpdateActorOutbox` run *before* `CreateFinderParticipantNode`. This ensures
the finder receives `Create(Case)` before `Add(CaseParticipant)`, preventing
"case not found" warnings on the finder side. Updated the module docstring to
document the ordering rationale.

**Files changed**:

- `vultron/core/behaviors/case/receive_report_case_tree.py` — reordered
  sequence children, updated docstring
- `test/core/behaviors/case/test_receive_report_case_tree.py` — added
  `test_create_case_precedes_add_participant_in_outbox`

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1399 passed, 10 skipped, 5581 subtests passed in 59.08s`

### D5-7-TRIGNOTIFY-1 — Populate `to` field in all trigger-use-case outbound activities

All trigger use cases that emit outbound state-change activities now populate
the `to` field so that case participants receive the notifications.

**Files changed**:

- `vultron/core/use_cases/triggers/_helpers.py` — added `case_addressees(case,
  excluding_actor_id) -> list[str]` helper; returns all actor IDs from
  `case.actor_participant_index` excluding the triggering actor
- `vultron/core/use_cases/triggers/case.py` — both `SvcEngageCaseUseCase` and
  `SvcDeferCaseUseCase` now pass `to=case_addressees(case, actor_id) or None`
  to `RmEngageCaseActivity` / `RmDeferCaseActivity`
- `vultron/core/use_cases/triggers/embargo.py` — `SvcProposeEmbargoUseCase`,
  `SvcEvaluateEmbargoUseCase`, and `SvcTerminateEmbargoUseCase` now pass
  `to=case_addressees(case, actor_id) or None` to their outbound activities
- `vultron/core/use_cases/triggers/report.py` — added `_report_addressees()`
  helper (looks up case via `find_case_by_report_id`, falls back to offer
  actor); `SvcInvalidateReportUseCase`, `SvcRejectReportUseCase`, and
  `SvcCloseReportUseCase` now pass `to=_report_addressees(...)`; added
  `is_case_model` guard to fix mypy type error
- `test/core/use_cases/triggers/__init__.py` — new empty init
- `test/core/use_cases/triggers/conftest.py` — vocab registry import
- `test/core/use_cases/triggers/test_trignotify.py` — 10 new tests covering
  all trigger use cases; verify `to` is populated, contains the other
  participant, and excludes the triggering actor

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1409 passed, 10 skipped, 5581 subtests passed in 69.59s`

---

## D5-7-EMSTATE-1 — Embargo initialization must update CaseStatus EM state

**Completed**: Priority 320

**Problem**: After `InitializeDefaultEmbargoNode` created and attached a
default embargo to a case, `CaseStatus.em_state` remained `EM.NONE`. The
embargo was created and stored as `active_embargo` but the state machine
position was never updated.

**Fix**:

- `vultron/core/behaviors/case/nodes.py`: Added `EM` import; in
  `InitializeDefaultEmbargoNode.update()`, after attaching the embargo,
  now sets `stored_case.current_status.em_state = EM.PROPOSED` and calls
  `stored_case.record_event(embargo.id_, "embargo_initialized")`.
- `vultron/demo/two_actor_demo.py`: Updated final-state assertion from
  `EM.NO_EMBARGO` to `EM.PROPOSED`; the demo creates a default embargo but
  does not negotiate it away, so `PROPOSED` is the correct final state.
- `test/core/behaviors/case/test_receive_report_case_tree.py`: Added 3 new
  tests verifying the EM state update, event recording, and idempotency guard.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1412 passed, 10 skipped, 5581 subtests passed in 70.18s`

---

## D5-7-AUTOENG-2 — Auto-cascade validate → engage (2026-04-14)

**Task**: After a successful `validate-report` trigger, automatically invoke
`engage-case` so demos and integrations no longer need a separate manual step.

**Changes**:

- `vultron/core/use_cases/received/case.py`: Added `_auto_engage()` helper to
  `ValidateCaseUseCase`; called on BT `SUCCESS` (received-message path).
- `vultron/core/use_cases/triggers/report.py`: Added `_auto_engage()` helper to
  `SvcValidateReportUseCase`; called on BT `SUCCESS` (trigger path). Captures
  `bridge.execute_with_setup()` result.
- `vultron/demo/two_actor_demo.py`: Removed manual `engage-case` trigger step
  (step 5 now describes the auto-cascade, not a separate call).
- `test/core/use_cases/received/test_report.py`: Updated descriptions;
  added `test_full_flow_vendor_auto_engages_after_validate`.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1413 passed, 10 skipped, 5581 subtests passed in 84.37s`

## D5-7-DEMONOTECLEAN-1 — Use trigger API for notes in two-actor demo

**Completed**: 2026-04-17

**Summary**: Replaced the two-actor demo's direct inbox POSTs (`Create(Note)` +
`AddNoteToCase`) with proper trigger API calls so that finder notes flow through
the finder's outbox rather than being posted directly to the vendor's inbox.
Vendor replies similarly use the vendor's trigger endpoint.

**Changes**:

- `vultron/core/use_cases/triggers/requests.py`: Added `AddNoteToCaseTriggerRequest`.
- `vultron/core/use_cases/triggers/note.py`: New `SvcAddNoteToCaseUseCase` —
  creates note in DataLayer, adds to local case.notes, queues `Create(Note)` and
  `AddNoteToCase` in actor outbox with `to` populated from case participants.
- `vultron/core/use_cases/triggers/__init__.py`: Exported `SvcAddNoteToCaseUseCase`.
- `vultron/adapters/driving/fastapi/trigger_models.py`: Added `AddNoteToCaseRequest`.
- `vultron/adapters/driving/fastapi/_trigger_adapter.py`: Added `add_note_to_case_trigger`.
- `vultron/adapters/driving/fastapi/routers/trigger_case.py`: Added
  `trigger_add_note_to_case` endpoint at `/{actor_id}/trigger/add-note-to-case`.
- `vultron/demo/two_actor_demo.py`: Rewrote `finder_asks_question` and
  `vendor_replies_to_question` to use trigger endpoints; added
  `wait_for_note_in_case` helper; removed now-unused `AddNoteToCaseActivity`
  and `as_Create` imports.
- `test/core/use_cases/triggers/test_note_trigger.py`: 12 new tests covering note
  creation, DataLayer persistence, outbox queuing, `to` field population, and
  `in_reply_to` handling.
- `test/demo/test_two_actor_demo.py`: Updated test calls to pass new
  `finder_client` parameter to `finder_asks_question`.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1425 passed, 10 skipped, 5581 subtests passed in 83.31s`

---

### D5-7-BTFIX-1 + D5-7-BTFIX-2 — BT cascade violations refactored to proper

subtrees

**Date**: 2026-04-17

**Tasks**: D5-7-BTFIX-1, D5-7-BTFIX-2 (Priority 320)

**Summary**: Eliminated two categories of BT cascade violation (BT-06-005,
BT-06-006) where protocol-observable RM state transitions were triggered
procedurally after `bt.run()` returned rather than as proper BT subtrees.

**Changes**:

- `vultron/core/behaviors/report/nodes.py`: added two new `DataLayerAction`
  nodes — `EmitEngageCaseActivity` (creates `RmEngageCaseActivity`/Join and
  adds to actor outbox) and `EmitDeferCaseActivity` (creates
  `RmDeferCaseActivity`/Leave and adds to actor outbox).
- `vultron/core/behaviors/report/prioritize_tree.py`: added
  `create_prioritize_subtree(case_id, actor_id)` factory. Builds a Selector
  `PrioritizeBT` with an EngagePath (EvaluateCasePriority → EmitEngage →
  TransitionRMtoAccepted) and a DeferPath (EmitDefer →
  TransitionRMtoDeferred).
- `vultron/core/behaviors/report/validate_tree.py`: extended
  `create_validate_report_tree` to accept optional `case_id`/`actor_id`;
  when provided, appends the PrioritizeBT as a child.
- `vultron/core/use_cases/triggers/report.py`: removed `_auto_engage()` from
  `SvcValidateReportUseCase`; passes `case_id`/`actor_id` to validate tree.
- `vultron/core/use_cases/received/case.py`: removed `_auto_engage()` from
  `ValidateCaseUseCase`; passes `case_id`/`actor_id` to validate tree.
- `vultron/core/use_cases/received/actor.py`: replaced procedural
  `SvcEngageCaseUseCase().execute()` call in
  `AcceptInviteActorToCaseReceivedUseCase` with BT bridge execution of a
  `PrioritizeBT` subtree.
- `vultron/core/use_cases/_helpers.py`: promoted `case_addressees()` helper
  from `triggers/_helpers.py` to the core module to break a circular import
  (`nodes.py → triggers._helpers → triggers/__init__ → report.py →
  validate_tree → nodes.py`).
- `notes/bt-integration.md`: updated to document the new PrioritizeBT
  structure and `create_prioritize_subtree` factory.
- Tests: `test/core/behaviors/report/test_prioritize_tree.py` (15 new tests),
  `test/core/behaviors/report/test_validate_tree.py` (updated).

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 new errors (11 pre-existing pyright
  errors in `test_note_trigger.py` unchanged)
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1428 passed, 10 skipped, 5581 subtests passed in 83.60s`

---

## OUTBOX-MON-1 — OutboxMonitor background loop (COMPLETE 2026-04-11)

**Task**: Implement a background outbox-drain loop (OUTBOX-MON-1) that
periodically scans all registered actor-scoped DataLayer instances and
delivers pending outbox activities to recipient inboxes automatically,
without requiring a manual trigger.

**Files changed**:

- `vultron/adapters/driven/datalayer_tinydb.py`: Added
  `get_all_actor_datalayers()` factory function that returns a snapshot of
  the `_datalayer_instances` dict (all registered actor-scoped DataLayer
  instances).
- `vultron/adapters/driving/fastapi/outbox_monitor.py` (new): `OutboxMonitor`
  class with `drain_all()` async method, `_run_loop()` polling loop, and
  `start()` / `stop()` lifecycle methods. Polls every 1 second by default.
  Accepts injected `actor_datalayers_factory`, `shared_dl`, and `emitter`
  for testability.
- `vultron/adapters/driving/fastapi/app.py`: Updated `lifespan` to
  instantiate `OutboxMonitor`, call `monitor.start()` on startup and
  `monitor.stop()` on shutdown.
- `test/adapters/driving/fastapi/test_outbox_monitor.py` (new): 19 unit
  tests covering `drain_all()` (empty/non-empty outboxes, multi-actor,
  error handling, default factory, default shared_dl), and `start()`/`stop()`
  lifecycle (task creation, cancellation, double-start warning, restart).

**Design notes**:

- `drain_all()` resolves `get_all_actor_datalayers` lazily at call time (not
  captured at `__init__`) so that test patches targeting the module-level
  name are effective.
- Error handling: per-actor exceptions are caught and logged at ERROR level;
  other actors' outboxes continue to be processed.
- `asyncio.CancelledError` is caught in `_run_loop()` so the monitor stops
  cleanly when cancelled via `stop()`.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 new errors (11 pre-existing pyright
  errors in `test_note_trigger.py` unchanged)
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1447 passed, 10 skipped, 5581 subtests passed in 81.35s`

---

## SYNC-1 — Local append-only case event log with indexing (2026-04-11)

**Task**: Implement the core domain models for the canonical case event log
foundation required by `specs/sync-log-replication.md` SYNC-01 and
`specs/case-log-processing.md` CLP-01 through CLP-05. Also add the
leadership guard port to `BTBridge` per SYNC-09-003.

**Files created**:

- `vultron/core/models/case_log.py` — `CaseLogEntry`, `CaseEventLog`,
  `ReplicationState`, `GENESIS_HASH`, and canonical-serialisation helpers.
- `test/core/models/test_case_log.py` — 52 unit tests covering all new
  models and the BTBridge leadership guard.

**Files modified**:

- `vultron/core/behaviors/bridge.py` — Added `is_leader: Callable[[], bool]`
  port to `BTBridge.__init__` (default: `_default_is_leader`, always `True`).
  `execute_with_setup` now checks `is_leader()` and returns a FAILURE result
  immediately when the check fails (SYNC-09-003).

**What was implemented**:

1. **`CaseLogEntry`** (Pydantic `BaseModel`) — single canonical log entry:
   - `log_index` (int) — monotonically increasing, scoped to case
     (CLP-02-006, SYNC-01-002)
   - `disposition` (`"recorded"` | `"rejected"`) (CLP-02-004)
   - `term` (optional int) — Raft term, `None` for single-node (CLP-02-007)
   - `payload_snapshot` (dict) — normalized activity snapshot for replay
     (CLP-02-003, SYNC-08-002)
   - `prev_log_hash` (str) — predecessor entry hash; `GENESIS_HASH` for
     first entry (SYNC-01-003)
   - `entry_hash` (str) — SHA-256 of canonical content (auto-computed via
     `model_validator`; excludes itself from hashed fields) (SYNC-01-003)
   - `reason_code` / `reason_detail` — for rejected entries (CLP-02-005)
   - `verify_hash()` method for tamper detection
   - Canonical serialisation uses RFC 8785 JCS-compatible JSON
     (`sort_keys=True`, compact separators) (SYNC-01-005)

2. **`CaseEventLog`** — append-only hash-chained log per case (SYNC-01-001):
   - `append(object_id, event_type, disposition, ...)` — assigns
     `log_index`, chains `prev_log_hash` from `tail_hash`, computes
     `entry_hash` automatically
   - `entries` property — immutable tuple of all entries (both dispositions)
   - `recorded_entries` property — filtered projection of `"recorded"` entries
     only (CLP-04-001, CLP-04-003)
   - `tail_hash` property — hash of last recorded entry or `GENESIS_HASH`
   - `verify_chain()` — validates hash-chain and index sequence integrity
   - Rejected entries require `reason_code` (raises `ValueError` if absent)

3. **`ReplicationState`** (Pydantic `BaseModel`) — per-peer replication state
   tracking (SYNC-04-001, SYNC-04-002):
   - `peer_id` — full URI of participant actor
   - `last_acknowledged_hash` — defaults to `GENESIS_HASH` for new peers

4. **`BTBridge` leadership guard** (SYNC-09-003):
   - New `is_leader: Callable[[], bool]` constructor parameter
   - Default: `_default_is_leader` always returns `True` (single-node)
   - `execute_with_setup` returns FAILURE immediately when `is_leader()`
     is `False`, with a descriptive log warning

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1499 passed, 10 skipped, 5581 subtests passed in 80.97s`

## SYNC-2: One-way log replication (Announce(CaseLogEntry))

**Task**: Implement one-way log replication from CaseActor to Participant
Actors via `Announce(CaseLogEntry)` activities (Priority 330).

**Files created**:

- `vultron/core/models/case_log_entry.py` — `VultronCaseLogEntry(core.VultronObject)`
  with full hash-chain fields; auto-computes `id_` from `{case_id}/log/{log_index}`.
- `vultron/wire/as2/vocab/objects/case_log_entry.py` — re-exports core class
  and registers `VOCABULARY["CaseLogEntry"]` for DataLayer round-trips.
- `vultron/wire/as2/vocab/activities/sync.py` — `AnnounceLogEntryActivity(as_Announce)`
  with `object_: VultronCaseLogEntry | as_Link | str | None`.
- `vultron/core/models/events/sync.py` — `AnnounceLogEntryReceivedEvent`
  with `log_entry` property.
- `vultron/core/use_cases/received/sync.py` — `AnnounceLogEntryReceivedUseCase`
  (hash-chain validation, idempotency, persistence).
- `vultron/core/use_cases/triggers/sync.py` — `commit_log_entry_trigger()`
  (creates entry, fans out to participants).
- `test/core/use_cases/received/test_sync.py` — 9 tests (4 reconstruct-hash,
  5 use-case).

**Files modified**:

- `vultron/core/models/enums.py` — added `CASE_LOG_ENTRY = "CaseLogEntry"`.
- `vultron/core/models/events/base.py` — added `ANNOUNCE_CASE_LOG_ENTRY`.
- `vultron/core/models/events/__init__.py` — registered `AnnounceLogEntryReceivedEvent`.
- `vultron/core/models/protocols.py` — added `LogEntryModel` Protocol.
- `vultron/wire/as2/extractor.py` — added `AnnounceLogEntryPattern` and
  `_build_domain_kwargs` branch for `CASE_LOG_ENTRY`.
- `vultron/core/use_cases/use_case_map.py` — registered
  `AnnounceLogEntryReceivedUseCase`.
- `test/core/models/test_case_log.py` — fixed pre-existing mypy ignore code
  (`[assignment]` → `[index]`).

**Key design decision**: `VultronCaseLogEntry` extends `core.VultronObject`
(not `wire.VultronObject(as_Object)`) so it can be assigned to
`VultronEvent.object_: core.VultronObject`. Pydantic v2 accepts it in
`AnnounceLogEntryActivity.object_: VultronCaseLogEntry | as_Link | str | None`
since it is the first union member. `VOCABULARY["CaseLogEntry"]` is registered
manually (the `type_` value) since `core.VultronObject` does not trigger
`as_Base.__init_subclass__`.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` → 0 errors (491 files)
- `uv run pyright` → 0 new errors (18 pre-existing in `test_note_trigger.py`)
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1510 passed, 11 skipped, 5581 subtests passed in 83.42s`

---

## SYNC-2 + SYNC-3 — One-way log replication and full sync loop with retry/backoff

**Completed**: 2026-04-14

**Tasks**: SYNC-2, SYNC-3 (Priority 330)

**Summary**: Implemented one-way log replication from CaseActor to Participant
Actors via AS2 `Announce(CaseLogEntry)` activities (SYNC-2), and full sync loop
with retry/backoff and hash-mismatch conflict resolution via
`Reject(CaseLogEntry)` activities (SYNC-3).

### SYNC-2: One-way log replication

- Added `AnnounceLogEntryReceivedUseCase` in
  `vultron/core/use_cases/received/sync.py` that:
  - Validates `prev_log_hash` chain continuity (SYNC-03-001).
  - Appends the `CaseLogEntry` to the local log if the chain is valid.
  - Rejects (sends `Reject(CaseLogEntry)` with `context` set to
    last-accepted hash) on mismatch (SYNC-03-001, SYNC-03-002).
  - Is idempotent: duplicate hashes are silently ignored (SYNC-03-003).
- Added `AnnounceLogEntryActivity` in
  `vultron/wire/as2/vocab/activities/sync.py`.
- Added `AnnounceLogEntryPattern` in `vultron/wire/as2/extractor.py`.
- Added `ANNOUNCE_CASE_LOG_ENTRY` to `MessageSemantics` and registered
  `AnnounceLogEntryReceivedEvent` in `vultron/core/models/events/`.
- Added `announce_log_entry_trigger` in
  `vultron/core/use_cases/triggers/sync.py` for CaseActor-initiated fan-out
  to all participants.

### SYNC-3: Full sync loop with retry/backoff

- Added `RejectLogEntryReceivedUseCase` that:
  - Reads the `last_accepted_hash` from the rejection `context` field
    (falls back to `GENESIS_HASH`).
  - Persists per-peer `VultronReplicationState` (new model in
    `vultron/core/models/replication_state.py`).
  - Queues replay of all missing entries after `last_accepted_hash` via
    `replay_missing_entries_trigger`.
- Added `replay_missing_entries_trigger` in
  `vultron/core/use_cases/triggers/sync.py` that iterates the local log
  from `from_hash` onward and re-emits `AnnounceLogEntry` for each entry.
- Implemented delivery retry/backoff in
  `vultron/adapters/driven/delivery_queue.py`:
  - Module-level tuneable constants: `DEFAULT_MAX_RETRIES=3`,
    `DEFAULT_INITIAL_DELAY=0.5`, `DEFAULT_BACKOFF_MULTIPLIER=2.0`,
    `DEFAULT_MAX_DELAY=30.0`.
  - `_deliver_with_retry()` uses exponential backoff with jitter; logs ERROR
    after all retries exhausted (SYNC-04-001, SYNC-05-001).
- Added `RejectLogEntryActivity` in `vultron/wire/as2/vocab/activities/sync.py`.
- Added `RejectLogEntryPattern` in `vultron/wire/as2/extractor.py`.
- Added `REJECT_CASE_LOG_ENTRY` to `MessageSemantics` and registered
  `RejectLogEntryReceivedEvent` in `vultron/core/models/events/`.

**Files created**:

- `vultron/core/models/replication_state.py` — `VultronReplicationState`
  persistable model; `id_` auto-computed as `{case_id}/replication/{peer_id}`.
- `vultron/wire/as2/vocab/objects/replication_state.py` — wire-layer vocab
  registration for `VultronReplicationState`.
- `test/core/use_cases/received/test_reject_sync.py` — 15 tests for
  `RejectLogEntryReceivedUseCase` and `replay_missing_entries_trigger`.
- `test/adapters/driven/test_delivery_backoff.py` — 15 tests for
  `DeliveryQueueAdapter` retry/backoff behavior.

**Files modified**:

- `vultron/core/models/events/base.py` — added `ANNOUNCE_CASE_LOG_ENTRY`,
  `REJECT_CASE_LOG_ENTRY`.
- `vultron/core/models/events/sync.py` — added `AnnounceLogEntryReceivedEvent`,
  `RejectLogEntryReceivedEvent` with `last_accepted_hash` fallback to
  `GENESIS_HASH`.
- `vultron/core/models/events/__init__.py` — registered both new event types.
- `vultron/core/use_cases/received/sync.py` — added both use cases plus
  `_find_local_actor_id`, `_update_replication_state`, `_send_rejection`
  helpers.
- `vultron/core/use_cases/triggers/sync.py` — added
  `announce_log_entry_trigger` and `replay_missing_entries_trigger`.
- `vultron/core/use_cases/use_case_map.py` — registered both new use cases.
- `vultron/wire/as2/vocab/activities/sync.py` — added
  `AnnounceLogEntryActivity`, `RejectLogEntryActivity`.
- `vultron/wire/as2/extractor.py` — added both patterns.
- `vultron/adapters/driven/delivery_queue.py` — retry/backoff with exponential
  delay and ERROR-level exhaustion logging.
- `test/core/use_cases/received/test_sync.py` — added hash-mismatch rejection
  tests.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` → 0 errors
- `uv run pyright` → 0 new errors (23 pre-existing in `test_note_trigger.py`
  and `test_reject_sync.py`, matching existing pattern)
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1544 passed, 12 skipped, 5581 subtests passed in 435.02s`

---

## SYNC-TRIG-1 + D5-7-DEMOREPLCHECK-1 — Sync Log Entry Trigger and Finder

Replica Verification (COMPLETE 2026-04-14)

### SYNC-TRIG-1: `sync-log-entry` FastAPI trigger endpoint

Exposes `commit_log_entry_trigger` (already implemented in
`vultron/core/use_cases/triggers/sync.py`) via HTTP so demos and external
callers can exercise SYNC-2 log replication end-to-end.

- Created `vultron/adapters/driving/fastapi/routers/trigger_sync.py` with
  `POST /actors/{actor_id}/trigger/sync-log-entry`.
  - Request body: `SyncLogEntryRequest { case_id, object_id, event_type }`.
  - Response: `{ log_entry_id, entry_hash, log_index }`.
  - Resolves short `actor_id` path param to canonical URI before calling
    `commit_log_entry_trigger`.
  - Schedules `outbox_handler` as background task (consistent with other
    trigger endpoints).
- Added `SyncLogEntryRequest` to
  `vultron/adapters/driving/fastapi/trigger_models.py`.
- Registered `trigger_sync.router` in
  `vultron/adapters/driving/fastapi/routers/v2_router.py`.
- Created `test/adapters/driving/fastapi/routers/test_trigger_sync.py`
  (11 tests).

### D5-7-DEMOREPLCHECK-1: Finder replica verification in two-actor demo

Added Step 6 to `run_two_actor_demo` that:

1. Commits a log entry on the vendor via the new `sync-log-entry` trigger.
2. Polls the finder's DataLayer until the entry appears (proving SYNC-2
   replication).
3. Verifies four replica invariants: same case ID, matching
   `actor_participant_index` keys, same `active_embargo` ID, and at least
   one committed log entry in the finder's DataLayer.

New functions in `vultron/demo/two_actor_demo.py`:

- `trigger_log_commit()` — calls `POST /trigger/sync-log-entry`, returns
  `entry_hash`.
- `wait_for_finder_log_entry()` — polls `/datalayer/CaseLogEntrys/` with
  timeout.
- `_extract_ref_id()` — safely extracts string ID from
  `str | as_Link | EmbargoEvent | None` union.
- `_get_log_entries_for_case()` — filters DataLayer log entries by `case_id`.
- `verify_finder_replica_state()` — asserts four cross-actor invariants.

Added 3 test classes to `test/demo/test_two_actor_demo.py`:
`TestTriggerLogCommit`, `TestWaitForFinderLogEntry`,
`TestVerifyFinderReplicaState`.

**Files created**:

- `vultron/adapters/driving/fastapi/routers/trigger_sync.py`
- `test/adapters/driving/fastapi/routers/test_trigger_sync.py`

**Files modified**:

- `vultron/adapters/driving/fastapi/trigger_models.py`
- `vultron/adapters/driving/fastapi/routers/v2_router.py`
- `vultron/demo/two_actor_demo.py`
- `test/demo/test_two_actor_demo.py`

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` → 0 errors
- `uv run pyright` → 0 new errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1562 passed, 12 skipped, 5581 subtests passed`

---

## BUG-2026041001 — Fix slow test suite (>15min → ~13s)

**Issue**: The test suite ran for >15 minutes (target: ~1 minute).
`test/demo/` accounted for 15m48s, with `test_two_actor_demo.py` alone taking
10m40s.

**Root cause**: TinyDB's `JSONStorage` re-reads and re-writes the entire JSON
file on every single operation. The default path `mydb.json` grew across
hundreds of tests, compounding the I/O penalty to >15 minutes.
`_DEFAULT_DB_PATH` is captured at module import time, making env-var patching
after import ineffective. A second issue: `test_default_db_path_uses_vultron_db_path_env_var`
called `importlib.reload()`, recreating `TinyDbDataLayer` as a new (unpatched)
class and breaking subsequent tests.

**Resolution**:

1. `pytest_configure` hook in `test/conftest.py` patches
   `TinyDbDataLayer.__init__` at session start, forcing `db_path=None`
   (MemoryStorage) for every instance anywhere in the test process.
2. `test/demo/conftest.py` marks all demo tests `@pytest.mark.integration`
   and adds a module-scoped autouse fixture to reset the datalayer between
   test modules.
3. `pyproject.toml` adds `addopts = "-m 'not integration'"` so the default
   run skips integration tests.
4. `test/adapters/driven/conftest.py` adds an autouse fixture that re-applies
   the in-memory patch after any test that calls `importlib.reload()`.
5. Two file-backed tests marked `@pytest.mark.integration`.
6. `test/test_datalayer_in_memory.py` added as regression guard (3 tests).
7. `.github/skills/run-tests/SKILL.md` updated to document both suites.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` → 0 errors
- `uv run pyright` → 11 pre-existing errors (unchanged)
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1384 passed, 12 skipped, 181 deselected, 5581 subtests passed in 13.31s`
- `uv run pytest -m integration --tb=short 2>&1 | tail -5` →
  `179 passed in 5.60s`

---

## PRIORITY-325 — TinyDB to SQLModel/SQLite DataLayer Migration (DL-SQLITE-ADR through DL-SQLITE-5)

**Completed**: 2026-07

### Summary

Replaced the TinyDB-backed `datalayer_tinydb.py` adapter with a new
SQLModel/SQLite implementation (`datalayer_sqlite.py`). All callers updated;
TinyDB fully removed from the codebase.

### Files Created

- `vultron/adapters/driven/datalayer_sqlite.py` — `SqliteDataLayer`
  implementation using SQLModel, single-table polymorphic schema
  (`VultronObjectRecord`, `QueueEntry`), actor-scoped queries,
  `get_datalayer()` factory, `reset_datalayer()`.
- `vultron/adapters/driven/datalayer.py` — Stable re-export facade.
- `test/adapters/driven/test_sqlite_backend.py` — Comprehensive unit and
  integration tests for the new backend.

### Files Deleted

- `vultron/adapters/driven/datalayer_tinydb.py`
- `test/adapters/driven/test_tinydb_backend.py`

### Key Changes

- `pyproject.toml`: removed `tinydb`, added `sqlmodel>=0.0.38`.
- `test/conftest.py`: sets `VULTRON_DB_URL=sqlite:///:memory:` before all
  imports; session-scoped `cleanup_test_datalayer` fixture calls
  `reset_datalayer()`.
- `docker/docker-compose-multi-actor.yml`: renamed env var from
  `VULTRON_DB_PATH` to `VULTRON_DB_URL`.
- 13+ `vultron/adapters/driving/` files and 30+ `test/` files: import path
  updated from `datalayer_tinydb` to `datalayer` facade.
- `get_datalayer()` reads `VULTRON_DB_URL` from `os.environ` at call time
  (not just at import time), improving test isolation.

### Notable Implementation Details

- `extend_existing=True` on SQLModel table classes prevents errors on module
  reimport.
- Custom `json_serializer` passed to `create_engine()` ensures `datetime`
  objects in JSON columns serialise as ISO-8601 strings.
- `_owns_engine` flag on `SqliteDataLayer` prevents `__del__` from disposing
  a borrowed engine when two instances share an engine for testing.
- `reset_datalayer()` drops and recreates tables but does NOT dispose engines
  (disposing an in-memory engine destroys its data).

> **Note (2026-04-14):** The description of `reset_datalayer()` above was
> superseded by the ResourceWarning fix below. It now calls `inst.close()`
> (which disposes engines) and no longer runs DDL on abandoned engines.

### Validation

- All four linters (black, flake8, mypy, pyright) pass with zero errors.
- `uv run pytest --tb=short 2>&1 | tail -5` gives
  `1402 passed, 13 skipped, 5581 subtests passed in ~20s`

---

## Fix: SQLite ResourceWarning Test Failures (2026-04-14)

**Commit:** `e49c1153`

### Problem

`uv run pytest` reported `17 failed, 18 errors` with the root cause being
`ResourceWarning: unclosed database in <sqlite3.Connection>`.

`filterwarnings = ["error"]` in `pyproject.toml` promotes `ResourceWarning`
to test errors. Python's cyclic GC does not guarantee `__del__` call order
within a reference cycle, so `engine.dispose()` was firing too late — or
not at all. Pytest's `unraisableexception` plugin catches these warnings via
`sys.unraisablehook` and attributes them to the *currently running* test,
not the test that created the leak, causing unrelated tests to fail.

### Root Causes

1. **`reset_datalayer()` never disposed engines.** It set
   `_shared_instance = None` / `_actor_instances = {}` but left engines
   alive. The orphaned `SqliteDataLayer` instances were eventually collected
   by cyclic GC, firing `ResourceWarning` during an unrelated test. The
   subsequent `drop_all`/`create_all` DDL calls operated on abandoned engines,
   creating a fresh connection that was immediately leaked again.

2. **Three test helpers orphaned Engine A.** The pattern:

   ```python
   dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)  # Engine A
   scoped._engine = dl._engine   # scoped now uses Engine B; Engine A abandoned
   scoped._owns_engine = False
   ```

   Engine A was never disposed. Affected files:
   `test_note_trigger.py`, `test_case.py`, `test_note.py`.

3. **Three router fixture teardowns were no-ops.** Fixtures created
   `SqliteDataLayer` instances directly (not via `get_datalayer()`), so they
   never appeared in `_actor_instances`. The teardown call
   `reset_datalayer(actor_id)` found nothing to reset, leaving the instances
   open until GC collected them.

### Fix

- **`datalayer_sqlite.py`**: Added `__enter__`/`__exit__` context manager
  to `SqliteDataLayer` (calls `self.close()` on exit). Rewrote
  `reset_datalayer()` to collect all cached instances, clear the global
  dictionaries, then call `inst.close()` on each — ensuring engines are
  disposed before references are dropped. Removed the orphan-creating
  `drop_all`/`create_all` DDL.

- **`test_note_trigger.py`**, **`test_case.py`**, **`test_note.py`**: Added
  `scoped._engine.dispose()` (or `scoped_dl._engine.dispose()`) before the
  engine swap to avoid orphaning the original engine.

- **`test_trigger_report.py`**, **`test_trigger_embargo.py`**,
  **`test_trigger_case.py`**: Changed fixture teardown to call
  `actor_dl.close()` explicitly instead of relying on `reset_datalayer()`.

### Validation

- All four linters (black, flake8, mypy, pyright) pass with zero errors.
- `uv run pytest --tb=short 2>&1 | tail -5`:
  `1402 passed, 13 skipped, 182 deselected, 5581 subtests passed`

### Lessons Learned

- `reset_datalayer()` must dispose engines *before* clearing references, not
  rely on GC. "Clear the reference, GC will clean up" is unsafe for
  resources that emit `ResourceWarning` on finalisation.
- The engine-swap pattern (`scoped._engine = new_dl._engine`) must always
  dispose the old engine first; otherwise the old engine is silently
  orphaned.
- Pytest `filterwarnings = ["error"]` + `ResourceWarning` + cyclic GC =
  test-contamination failures that appear in unrelated tests. When tests
  fail with `ResourceWarning` about unclosed resources, look for orphaned
  instances in fixture teardowns and helper functions, not in the failing
  test itself.
- `__enter__`/`__exit__` on `SqliteDataLayer` allows safe use in test
  helpers via `with SqliteDataLayer(...) as dl:`, preventing technical debt
  from per-call dispose boilerplate.

## BUG-26041501 — Two-actor demo Finder crash on Announce(CaseLogEntry) [2026-04-15]

**Issue**: The Vendor (CaseActor) fans out a `Announce(CaseLogEntry)` to the
Finder. The Finder receives the activity with `object: "urn:uuid:.../log/0"`
(a plain URI string), cannot resolve it to a typed `CaseLogEntry`, and crashes
with `AttributeError: 'VultronObject' object has no attribute 'case_id'`.

**Root Cause**: A 6-point failure chain:

1. `dl.save(announce)` dehydrates `object_` to URI string via `_dehydrate_data`
2. `handle_outbox_item` only expands `object_` for `Create`, not `Announce`
3. Even with inline dict, `parse_activity` dropped CaseLogEntry fields (bare
   `as_Object` with `extra="ignore"`)
4. `VultronCaseLogEntry` extends core `VultronObject` (NOT wire `as_Object`),
   so `rehydrate()` rejects it; no wire-layer `CaseLogEntry` class existed
5. Extractor got bare `VultronObject`; CASE_LOG_ENTRY branch did not fire
6. Use case crashed on `entry.case_id` AttributeError

**Resolution**: 7 coordinated fixes across 6 files:

1. `vultron/wire/as2/vocab/objects/case_log_entry.py`: New wire `CaseLogEntry`
   class inheriting from `VultronObject` (wire, `as_Object` subclass), with all
   domain fields and auto-registration in `VOCABULARY["CaseLogEntry"]`.
2. `vultron/wire/as2/vocab/activities/sync.py`: `AnnounceLogEntryActivity` and
   `RejectLogEntryActivity` use wire `CaseLogEntry` for `object_`; removed
   `# type: ignore[assignment]` annotations.
3. `vultron/core/use_cases/triggers/sync.py`: Added `_to_wire_entry()` helper;
   both fan-out and replay paths now convert to wire `CaseLogEntry` before
   constructing activities.
4. `vultron/adapters/driving/fastapi/outbox_handler.py`: Object expansion
   extended from `"Create"` to `("Create", "Announce")`.
5. `vultron/wire/as2/parser.py`: Added `_expand_inline_object()` pre-processor
   that resolves inline object dicts to typed vocabulary instances before outer
   activity validation, preserving all subtype-specific fields.
6. `vultron/core/use_cases/received/sync.py`: Added `isinstance` guard for
   graceful error handling; `_send_rejection` uses `entry.id_` string.
7. `specs/sync-log-replication.md`: Added `SYNC-02-004` requiring full inline
   `CaseLogEntry` in `Announce` activities.

**Tests added/updated**: `test_inline_case_log_entry_round_trip` in
`test_sync.py` reproduces the parse → extract → log_entry.case_id failure path.
Test helpers in `test_sync.py` and `test_reject_sync.py` updated to use wire
`CaseLogEntry`. 1404 tests pass (5 new).

## ARCH-01-001 Fix + Wire Translation Boundary Design [2026-04-15]

### from_core() Refactor (commit f8eede75)

Review of commit `87961536` (BUG-26041501) identified an ARCH-01-001 violation:
`_to_wire_entry()` in `vultron/core/use_cases/triggers/sync.py` was a core
module importing from `vultron.wire` and embedding conversion logic. The fix
moves conversion ownership to the wire type:

- Added `WireCaseLogEntry.from_core(cls, entry: VultronCaseLogEntry)` classmethod
  in `vultron/wire/as2/vocab/objects/case_log_entry.py` using JSON round-trip:
  `cls.model_validate(entry.model_dump(mode="json"))`
- Removed `_to_wire_entry()` from `vultron/core/use_cases/triggers/sync.py`
- Updated both call sites to `WireCaseLogEntry.from_core(entry)`

1404 tests pass; all linters clean.

### Architecture Design Session (grill-me on PROTO-06-001)

Extended design conversation established these decisions (captured in
`specs/architecture.md` ARCH-12-001 through ARCH-12-007):

**Key finding**: Domain objects are already pure Pydantic BaseModel — they do
NOT inherit from AS2 types. PROTO-06-001's structural concern is resolved.
PROTO-06-001 removed from `specs/prototype-shortcuts.md`.

**Two VultronObject classes**: `vultron.core.models.base.VultronObject` (domain
base, pure Pydantic) and `vultron.wire.as2.vocab.objects.base.VultronObject`
(AS2 wire base) cause confusion. Wire version to be renamed `VultronAS2Object`.

**Decisions made**:

1. Wire base renamed `VultronAS2Object` (ARCH-12-001)
2. `from_core(cls, core_obj)` classmethod on all wire types; base raises
   `NotImplementedError`; default uses JSON round-trip (ARCH-12-002, 007)
3. `to_core(self)` instance method on all wire types; base raises
   `NotImplementedError` (ARCH-12-003)
4. `_field_map: ClassVar[dict[str, str]] = {}` escape hatch for field name
   mismatches (ARCH-12-004)
5. Generic `from_core(domain_activity)` on wire activity base class mapping
   grammatical AS2 fields (ARCH-12-005)
6. `vultron/wire/as2/serializer.py` to be deleted; callers migrated to
   `WireType.from_core()` (ARCH-12-006)
7. Once WIRE-TRANS-05 completes, trigger modules' direct wire imports are
   unnecessary → closes remaining ARCH-01-001 violations

**Meta-policy decision**: Superseded specs MUST be removed, not deprecated.
Deprecated specs are agent noise. Added to `specs/meta-specifications.md`.

**Documentation updates**:

- `specs/architecture.md`: ARCH-12 section added; review checklist and
  remediation status updated; PROTO-06-001 references removed
- `specs/prototype-shortcuts.md`: PROTO-06-001 section replaced with removal
  comment
- `specs/case-management.md`: CM-08-002 upgraded from SHOULD to MUST, updated
  to reflect current clean inheritance status
- `specs/meta-specifications.md`: "Lifecycle of Superseded Requirements"
  section added
- `notes/domain-model-separation.md`: "Current Status" completely rewritten
  to reflect 2026-04-15 findings; "Recommended Next Steps" updated to
  reference WIRE-TRANS-01 task
- `plan/IMPLEMENTATION_PLAN.md`: PRIORITY-340 / WIRE-TRANS-01–05 task block
  added; header updated (refresh #74)
- `plan/IMPLEMENTATION_NOTES.md`: 2026-04-15 session notes appended

---

### WIRE-TRANS-01 (shim removal) + WIRE-TRANS-02 (from_core/to_core)

**Date**: 2026-04-15

**WIRE-TRANS-01 completion** — removed the `VultronObject = VultronAS2Object`
backward-compatibility alias from `vultron/wire/as2/vocab/objects/base.py`.
No external callers of the wire-layer alias existed; all `VultronObject`
references in the codebase import from `vultron.core.models.base` (the core
domain type), not from the wire module.

**WIRE-TRANS-02** — added to `VultronAS2Object`:

- `_field_map: ClassVar[dict[str, str]] = {}` — class variable for
  domain-to-wire field name translation; subclasses override when wire field
  names differ from core field names.
- `from_core(cls, core_obj: Any) -> "VultronAS2Object"` — default JSON
  round-trip implementation: `core_obj.model_dump(mode="json")`, apply
  `_field_map` renames, then `cls.model_validate(data)`. Subclasses narrow
  the parameter type and can override for complex cases.
- `to_core(self) -> Any` — raises `NotImplementedError`; subclasses with a
  well-defined reverse mapping SHOULD override.

Docstrings document the `_field_map` contract and expected subclass narrowing.

`from_core()` provides a working default (not a bare `NotImplementedError`
stub) because the `CaseLogEntry.from_core()` already demonstrated the pattern
and it is uniform enough to be a safe base-class default.

**Files changed**:

- `vultron/wire/as2/vocab/objects/base.py` — shim removed; `_field_map`,
  `from_core()`, `to_core()` added
- `test/wire/as2/vocab/test_vultron_as2_object.py` — 14 new tests
- `plan/IMPLEMENTATION_PLAN.md` — WIRE-TRANS-01, WIRE-TRANS-02 marked done;
  header updated (refresh #75)
- `plan/IMPLEMENTATION_HISTORY.md` — this entry

**Test counts**: 1418 passed, 12 skipped (up from 1404; +14 new tests).

---

## WIRE-TRANS-03 — Concrete wire object/domain conversions

**Date**: 2026-04-15

**Task**: Implement `from_core()` on concrete wire object types and add
`to_core()` where the reverse mapping is well-defined.

**What was done**:

- Added shared helpers to `vultron/wire/as2/vocab/objects/base.py` for
  reference-ID normalization and reverse field-map application.
- Implemented concrete `from_core()` / `to_core()` methods on:
  - `VulnerabilityReport`
  - `CaseStatus`
  - `ParticipantStatus`
  - `CaseParticipant`
  - `VulnerabilityCase`
  - `CaseLogEntry`
  - `CaseActor`
- `VulnerabilityCase.from_core()` now materializes string-only `case_activity`
  entries as minimal `as_Activity` objects for wire validation, while
  `to_core()` collapses them back to ID strings.
- Reverse translation of nested wire objects now routes through each nested
  object's own `to_core()` implementation so enum-valued state fields survive
  the round-trip cleanly.
- Added focused regression coverage in
  `test/wire/as2/vocab/test_wire_domain_translation.py`.

**Validation**:

- `uv run black vultron/ test/`
- `uv run flake8 vultron/ test/`
- `uv run mypy`
- `uv run pyright`
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1425 passed, 12 skipped, 182 deselected, 5581 subtests passed in 23.29s`

---

## WIRE-TRANS-04 + WIRE-TRANS-05 — Activity wire base + delete serializer.py

**Tasks**: WIRE-TRANS-04, WIRE-TRANS-05 (Priority 340)

**What was done**:

- **WIRE-TRANS-04**: Created `vultron/wire/as2/vocab/activities/base.py`
  containing `VultronAS2Activity(as_TransitiveActivity)`. The class provides a
  generic `from_core(cls, domain_activity: VultronActivity) -> VultronAS2Activity`
  classmethod that converts a domain activity via JSON round-trip
  (`model_dump(mode="json")` + `model_validate`), with optional `_field_map`
  rename support for subclasses. Subclasses narrow the parameter type annotation.
  The module is auto-discovered by the existing `activities/__init__.py` package
  discovery mechanism.
- **WIRE-TRANS-05**: Deleted `vultron/wire/as2/serializer.py` (6 unused
  `domain_xxx_to_wire()` functions; confirmed zero callers in codebase).
- Added 4 tests to `test/wire/as2/vocab/test_wire_domain_translation.py`
  covering: string-field activity, None-object activity, `_field_map` rename
  subclass, and Accept domain subtype.

**Validation**:

- `uv run black vultron/ test/`
- `uv run flake8 vultron/ test/`
- `uv run mypy` → `Success: no issues found in 501 source files`
- `uv run pyright` → `0 errors, 0 warnings, 0 informations`
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1430 passed, 12 skipped, 182 deselected, 5581 subtests passed in 19.30s`

## Spec Token-Overhead Reduction (6-pass cleanup)

Reduced agent token overhead in `specs/` corpus while keeping all
transformations semantically lossless. Total savings ~18 KB (~5% of corpus).

**Changes**:

  Load Contextually by topic). Replaced stale 2026-03-26 Implementation Status
  snapshot with pointer to `plan/IMPLEMENTATION_PLAN.md`.

- `specs/vultron-protocol-spec.md`: Stripped 194 per-requirement `Source: docs/...`
  sub-bullets (~11 KB). Header `**Sources**:` block preserves all referenced docs.
- `specs/architecture.md`: Removed 8 inline `**Current state**:` sub-bullets,
  `**Implemented**:` annotation on ARCH-12-002, and entire "Remediation Status"
  section. Added pointer to `notes/architecture-review.md`.
- `specs/code-style.md`: Removed superseded requirements CS-01-002, CS-01-003,
  CS-01-006 (superseded by `tech-stack.md` IMPL-TS-07-*). Trimmed verbose Rationale
  blocks to single sentences. Removed NAMING-1 commit reference from CS-07-003.
- `specs/behavior-tree-integration.md`: Condensed multi-line Rationale blocks
  for BT-06-001 and BT-06-004.
- `specs/testability.md`: Condensed multi-line Rationale block for TB-10-001.
- `AGENTS.md`: Removed `**Last Updated:** 2026-03-20` datestamp, "all remediated
  as of ARCH-CLEANUP" status annotation, and "Handler shims: removed in PREPX-2"
  entry from Key Files Map.

## BUG-26041601 — Fixed ownership-transfer dispatch error in multi-vendor demo

**Issue**: The multi-vendor demo crashed with
`AttributeError: 'NoneType' object has no attribute 'startswith'` when the
coordinator processed an `OfferCaseOwnershipTransferActivity`. The coordinator
incorrectly dispatched to `SubmitReportReceivedUseCase` instead of
`OfferCaseOwnershipTransferReceivedUseCase`, which then crashed trying to store
a malformed object.

**Root cause (two-layer)**:

1. `OfferCaseOwnershipTransferActivity` was constructed with
   `object_=case.id_` (a bare string URI) in `multi_vendor_demo.py` and
   `transfer_ownership_demo.py`. The receiving coordinator could not resolve the
   case from its DataLayer, so `object_` remained a string after rehydration.

2. `ActivityPattern._match_field` conservatively returns `True` for any string
   URI (can't type-check an opaque reference). Both `ReportSubmissionPattern`
   (SUBMIT_REPORT) and `OfferCaseOwnershipTransferActivityPattern`
   (OFFER_CASE_OWNERSHIP_TRANSFER) are `Offer` activities, so both matched.
   `SUBMIT_REPORT` appeared first in `SEMANTICS_ACTIVITY_PATTERNS`, winning
   the ambiguous match.

**Resolution**: Eliminated the ambiguity at its source by enforcing the
inline-object constraint in the Pydantic model:

- Changed `OfferCaseOwnershipTransferActivity.object_` from
  `VulnerabilityCaseRef` (`VulnerabilityCase | str | None`) to
  `VulnerabilityCase | None`. Pydantic now rejects bare string IDs at
  construction time.
- Fixed `multi_vendor_demo.py` and `transfer_ownership_demo.py` to pass
  `object_=case` (the full `VulnerabilityCase` object) instead of
  `object_=case.id_`.
- Added two regression tests to `test/test_semantic_activity_patterns.py`:
  `test_offer_case_ownership_transfer_rejects_string_object` (confirms
  validation error on string) and
  `test_offer_case_ownership_transfer_with_inline_case_dispatches_correctly`
  (confirms correct semantics with inline case).

**Files changed**:

- `vultron/wire/as2/vocab/activities/case.py`
- `vultron/demo/multi_vendor_demo.py`
- `vultron/demo/transfer_ownership_demo.py`
- `test/test_semantic_activity_patterns.py`

---

## INLINE-OBJ-A — Inline typed outbound activity objects (COMPLETE 2026-04-16)

- Narrowed initiating outbound AS2 activity `object_` fields from permissive
  `XxxRef` unions to inline typed objects across report, case, participant,
  embargo, actor, and sync activity classes.
- Added MV-09 outbound-object integrity enforcement in the outbox handler so
  delivery rejects bare string or `as_Link` `object_` values after a final
  expansion attempt.
- Fixed all remaining callers in demos, vocab examples, trigger fixtures, and
  received/trigger tests to pass inline domain objects instead of bare IDs.
- Normalized persisted embargo records in `SvcTerminateEmbargoUseCase` so
  SQLite `as_Event` round-trips can still be re-validated as `EmbargoEvent`
  before constructing `AnnounceEmbargoActivity`.
- Updated regression coverage for narrowed activity classes, outbox integrity,
  embargo trigger routes, and vocab example expectations.

## INLINE-OBJ-B — Accept/Reject inline typed objects (Priority 330)

- Changed `object_` type on all 12 `AcceptXxx` / `RejectXxx` /
  `TentativeRejectXxx` activity classes from `XxxRef`
  (`XxxActivity | as_Link | str | None`) to `XxxActivity | None`,
  preventing bare string IDs from passing Pydantic validation at
  construction time. Files: `actor.py`, `case.py`, `embargo.py`,
  `report.py`, `sync.py` in `vultron/wire/as2/vocab/activities/`.
- Updated `vultron/core/use_cases/triggers/report.py`:
  `_resolve_offer_and_report` now coerces the stored offer to
  `RmSubmitReportActivity` via `model_validate`; 3 callers updated to
  pass the full object to `object_`.
- Updated `vultron/core/use_cases/triggers/embargo.py`: added
  dehydration-aware coercion of stored `as_Invite` to
  `EmProposeEmbargoActivity` (strips dehydrated `object_` string from
  the serialized dict before validation; preserves the embargo event ID
  for the subsequent `dl.read` lookup); caller updated to pass the
  typed proposal as `object_`.
- Updated `vultron/core/use_cases/received/sync.py`: `_send_rejection`
  now constructs a `CaseLogEntry` via `CaseLogEntry.from_core(entry)`
  before passing it as `object_` to `RejectLogEntryActivity`.
- Updated `vultron/demo/utils.py`: `get_offer_from_datalayer` now
  coerces the retrieved `as_Offer` to `RmSubmitReportActivity`; all
  calling demo files benefit automatically.
- Fixed remaining `.id_` string IDs in `receive_report_demo.py` (7
  occurrences), `three_actor_demo.py` (2), `multi_vendor_demo.py` (1),
  and `status_updates_demo.py` (1).
- Updated `specs/response-format.md` RF-02-003/04, RF-03-003/04,
  RF-04-003/04 to require inline typed objects.
- Reversed "Accept/Reject object field" pitfall in `AGENTS.md` from
  "use ID string" to "use inline typed object"; also updated the
  Protocol Activity Model section.
- Added regression tests:
  `test/wire/as2/vocab/test_actvitities/test_inline_object_required.py`
  — 12 string-rejected tests + 12 typed-accepted tests.
- Lesson: the storage layer (`_dehydrate_data` in `db_record.py`)
  collapses `object_` of transitive activities to an ID string. Coercion
  back to a typed class must strip the dehydrated string and separately
  retrieve the nested object from `dl.read`.

---

## Phase INLINE-OBJ-C — Prohibit object_=None on semantic-dispatch classes (COMPLETE 2026-04-17)

Removed `| None` and `default=None` from `object_` fields on all 37 activity
classes in `vultron/wire/as2/vocab/activities/` where the `ActivityPattern`
inspects `object_.type` for semantic dispatch. An omitted or `None` `object_`
always caused `ActivityPattern._match_field` to return `False`, routing the
activity to `UNKNOWN`. Making `object_` required at construction time prevents
this class of silent dispatch failure.

### Files changed

- `vultron/wire/as2/vocab/activities/report.py` — 6 classes
- `vultron/wire/as2/vocab/activities/case.py` — 14 classes (not `RmInviteToCaseActivity`)
- `vultron/wire/as2/vocab/activities/actor.py` — 3 classes
- `vultron/wire/as2/vocab/activities/embargo.py` — 7 classes
- `vultron/wire/as2/vocab/activities/case_participant.py` — 5 classes;
  removed redundant `if self.object_ is not None:` guard in `set_name` validator
- `vultron/wire/as2/vocab/activities/sync.py` — 2 classes
- `vultron/core/use_cases/triggers/embargo.py` — replaced the
  `dehydrated_embargo_id`/strip-then-validate pattern with a data-layer
  resolution of `EmbargoEvent` before calling `model_validate`, so the coerced
  `EmProposeEmbargoActivity` always has a valid `object_: EmbargoEvent`
- `specs/message-validation.md` — added `MV-09-003` requirement and
  verification criteria
- `test/wire/as2/vocab/test_actvitities/test_inline_object_required.py` —
  expanded imports; added `TestNoneObjectRejected` with 74 tests (37 classes ×
  `object_=None` + missing `object_`)

### Test results at completion

1607 passed, 12 skipped, 182 deselected, 5581 subtests; `black`, `flake8`,
`mypy`, `pyright` all clean.

---

## BUG-26041602 — CommitCaseLogEntryNode composable BT node (2026-04-17)

### Problem

`CaseActor` never automatically emitted `Announce(CaseLogEntry)` sync messages
when processing inbound case activities (`create_case`, `engage_case`,
`defer_case`, `submit_report`). The two-actor demo worked around this by
explicitly calling `POST /actors/{id}/trigger/sync-log-entry` after each step.
The `commit_log_entry_trigger` service existed and was functional, but was never
wired into the BT execution path.

### Approach

Added `CommitCaseLogEntryNode` as a composable BT node (inheriting
`DataLayerAction`) that is the final child of each relevant case BT. The node:

1. Resolves `case_id` from constructor param (known at build time) or
   blackboard fallback (written by `CreateCaseNode` for `ReceiveReportCaseBT`).
2. Derives `event_type` from `activity.semantic_type.value` (on blackboard) or
   falls back to `"case_event"` when no activity is present.
3. Calls `commit_log_entry_trigger(case_id, object_id, event_type, actor_id, dl)`.
4. Returns `SUCCESS` silently (no-op) when `case_id` is unavailable.

`OutboxMonitor` remains the sole delivery mechanism — the node only writes to
the outbox, matching the reactive "on-new-item-do" pattern.

**Circular import resolved**: Removed package-level re-exports from
`vultron/core/use_cases/triggers/__init__.py`. The cycle was:
`nodes.py` → `triggers.sync` → `triggers/__init__.py` (re-exports `report`)
→ `triggers/report.py` → `validate_tree` → `prioritize_tree` → `nodes.py`.
No callers imported from the package level, so removing the re-exports was safe.

### Files changed

- `vultron/core/behaviors/case/nodes.py` — added `CommitCaseLogEntryNode`
- `vultron/core/behaviors/case/create_tree.py` — wired node as last child
- `vultron/core/behaviors/report/prioritize_tree.py` — wired node into both
  `EngageCaseBT` and `DeferCaseBT`
- `vultron/core/behaviors/case/receive_report_case_tree.py` — wired node as
  last child (blackboard `case_id` fallback)
- `vultron/core/use_cases/triggers/__init__.py` — removed package-level
  re-exports to break circular import
- `test/core/behaviors/case/test_commit_log_entry_node.py` — 7 new unit tests
- `test/core/behaviors/case/test_receive_report_case_tree.py` — updated
  flow-children count test (6 → 7)
- `test/core/behaviors/report/test_prioritize_tree.py` — updated
  `EngageCaseBT`/`DeferCaseBT` children count tests (2 → 3)

### Test results at completion

1614 passed, 12 skipped, 182 deselected, 5581 subtests; `black`, `flake8`,
`mypy`, `pyright` all clean.

---

## DL-REHYDRATE: DataLayer semantic type recovery

**Task**: PRIORITY-345 DL-REHYDRATE
**Completed**: 2026-05-20

### Summary

Implemented automatic field rehydration and semantic-class coercion in
`SqliteDataLayer._from_row` so that `dl.read()` always returns fully-typed
domain objects without requiring manual coercion in use cases.

### Changes

**`vultron/adapters/driven/datalayer_sqlite.py`**:

- Added `_rehydrate_fields()`: expands dehydrated string-ID fields
  (`object_`, `target`, `origin`, `result`, `instrument`) back to typed
  Pydantic objects via `self.read()`.
- Added `_coerce_to_semantic_class()`: pattern-matches rehydrated activities
  against `SEMANTICS_ACTIVITY_PATTERNS` and coerces to the most specific
  Python class registered in `SEMANTICS_TO_ACTIVITY_CLASS`.
- Updated `_from_row` to call both methods after `record_to_object`.

**`vultron/wire/as2/extractor.py`**:

- Added imports for all specific activity classes.
- Added `SEMANTICS_TO_ACTIVITY_CLASS: dict[MessageSemantics, type[as_Activity]]`
  with 34 entries — maps each semantic type to its specific Python class.

**`vultron/core/models/protocols.py`**:

- Added `model_copy` to `PersistableModel` Protocol to match Pydantic v2
  signature (`Mapping[str, Any] | None`).

**`vultron/core/use_cases/triggers/embargo.py`**:

- Removed large manual coercion block (previously lines 210-247) that
  dehydrated `EmProposeEmbargoActivity.object_` strings; replaced with a
  simple `isinstance` check since `dl.read()` now returns the correct type.
- Simplified `embargo is None` check by removing the `type_` string guard.

**`vultron/core/use_cases/triggers/report.py`**:

- Removed `rehydrate`, `as_Object`, and `PydanticValidationError` imports.
- Simplified `_resolve_offer_and_report` from 37 lines to 12 lines; now
  directly checks `isinstance(offer, RmSubmitReportActivity)` and
  `isinstance(report, VulnerabilityReport)`.

**`test/adapters/driven/test_sqlite_backend.py`**:

- Updated `test_reading_activity_back_yields_id_string_for_nested_object` →
  `test_reading_activity_back_yields_expanded_nested_object` to reflect new
  behavior.
- Added `TestRehydrateFields` and `TestCoerceToSemanticClass` test classes
  covering the round-trip for `RmSubmitReportActivity` and
  `EmProposeEmbargoActivity`.

**`test/core/behaviors/report/test_prioritize_tree.py`**,
**`test/core/use_cases/received/test_actor.py`**:

- Updated assertions from `object_ == case.id_` to `object_.id_ == case.id_`
  since `engage_activity.object_` is now a typed `VulnerabilityCase` object.

### Test results at completion

1619 passed, 12 skipped, 182 deselected, 5581 subtests; `black`, `flake8`,
`mypy`, `pyright` all clean.

---

## 2026-04-10 — VOCAB-REG-1.1: Redesign vocabulary registry core mechanics

- **Outcome**: SUCCESS
- **Summary**: Replaced the Pydantic `Vocabulary(BaseModel)` singleton with a
  plain `VOCABULARY: dict[str, type[BaseModel]]` module-level dict and switched
  auto-registration from explicit decorator calls to `__init_subclass__` hook in
  `as_Base`. Added `VocabNamespace` enum (`AS`, `VULTRON`). All class files
  updated to remove `@activitystreams_*` decorator imports while leaving the
  decorator definitions in place for the follow-on migration (VOCAB-REG-1.2).
- **Artifacts**:
  - `vultron/wire/as2/vocab/base/enums.py` — new `VocabNamespace` enum
  - `vultron/wire/as2/vocab/base/registry.py` — rewrote flat-dict registry,
    removed decorator definitions, updated `find_in_vocabulary()` to raise
    `KeyError` on miss
  - `vultron/wire/as2/vocab/base/base.py` (`as_Base`) — added
    `_vocab_ns: ClassVar[VocabNamespace]`, added `__init_subclass__`
    auto-registration hook
  - `vultron/wire/as2/vocab/objects/base.py` (`VultronObject`) — overrides
    `_vocab_ns = VocabNamespace.VULTRON`

---

## 2026-04-10 — VOCAB-REG-1.2: Migrate vocabulary classes and update callers

- **Outcome**: SUCCESS
- **Summary**: Completed the vocabulary registry migration by removing all
  `@activitystreams_*` decorator call sites (74 sites across 16 files), adding
  `pkgutil`/`importlib` dynamic discovery to four `__init__.py` files,
  explicitly registering `as_Actor`, updating all `find_in_vocabulary()` callers
  to handle `KeyError`, and adding a subclass-identity preservation fix to the
  registry decorators (returning `TypeVar`-based generic signature instead of
  `type[BaseModel]`). Test suite updated with new registry and completeness
  tests plus a regression test for BUG-26040902.
- **Artifacts**:
  - 16 vocab class files: removed `@activitystreams_object` /
    `@activitystreams_activity` / `@activitystreams_link` call sites
  - `vultron/wire/as2/vocab/objects/__init__.py`,
    `vultron/wire/as2/vocab/activities/__init__.py`,
    `vultron/wire/as2/vocab/base/objects/__init__.py`,
    `vultron/wire/as2/vocab/base/objects/activities/__init__.py` — added
    dynamic module discovery
  - `vultron/wire/as2/vocab/base/registry.py` — explicit `as_Actor`
    registration, `TypeVar` return type preservation
  - `vultron/wire/as2/parser.py` — activity-type guard (`issubclass` check)
  - `test/wire/as2/vocab/base/test_registry.py` — new unit tests
  - `test/wire/as2/vocab/base/test_registry_completeness.py` — new completeness
    tests
  - `test/core/behaviors/case/test_bug_26040902_regression.py` — regression
    test for BUG-26040902

---

## P347-BUGFIX + P347-NODEGENERAL: Fix and generalize CreateFinderParticipantNode

**Completed**: P347-BUGFIX (BUG-26041701) and P347-NODEGENERAL (IDEA-26041702)

### Summary

Fixed a bug in `CreateFinderParticipantNode` where `VultronActivity(type_="Add",
object_=participant.id_, ...)` used a bare string as `object_`, violating
MV-09-001 and causing `VultronOutboxObjectIntegrityError` after dehydration.

Simultaneously generalized the node to `CreateCaseParticipantNode(actor_id,
roles, report_id)`, removing the hard-coded finder/reporter coupling and
eliminating the runtime DataLayer offer lookup (the finder's actor ID is now
passed as a constructor argument from `SubmitReportReceivedUseCase`).

### Files Changed

- `vultron/core/behaviors/case/nodes.py` — replaced `CreateFinderParticipantNode`
  with `CreateCaseParticipantNode(actor_id, roles, report_id)`; removed unused
  `VultronActivity` import; added backward-compat alias; fixed object_ bug to use
  `AddParticipantToCaseActivity(object_=CaseParticipant)` with proper coercion
- `vultron/core/behaviors/case/receive_report_case_tree.py` — added
  `finder_actor_id: str` parameter to `create_receive_report_case_tree()`;
  updated `CreateCaseParticipantNode` invocation
- `vultron/core/use_cases/received/report.py` — pass `finder_actor_id=request.actor_id`
- `test/core/use_cases/received/test_report.py` — removed offer pre-storage
  (no longer needed); updated comments from `CreateFinderParticipantNode` to
  `CreateCaseParticipantNode`
- `test/core/behaviors/case/test_receive_report_case_tree.py` — added
  `finder_actor_id` fixture injection to all test functions
- `test/core/behaviors/report/test_validate_tree.py` — added `finder_actor_id`
  to `case` fixture
- `test/core/behaviors/case/test_bug_26040902_regression.py` — added
  `finder_actor_id=_finder_actor_id`
- `test/adapters/driving/fastapi/routers/test_trigger_report.py` — added
  `finder_actor_id=actor.id_`
- `test/adapters/driving/fastapi/test_trigger_services.py` — added
  `finder_actor_id=actor.id_`; restored `accepted_report` fixture

### Test Result

1619 passed, 12 skipped, 182 deselected, 5581 subtests passed

---

## P347-BRIDGE — Extend outbox expansion bridge (COMPLETE 2026-05-22)

**Task**: Extend the backward-compatibility expansion bridge in
`handle_outbox_item` from `("Create", "Announce")` to also include
`"Add"`, `"Invite"`, and `"Accept"` activity types. Added a TODO comment
noting that `"Join"` and `"Remove"` will need the same treatment when
implemented.

### Files Changed

- `vultron/adapters/driving/fastapi/outbox_handler.py`: Extended
  `activity_type in (...)` tuple; updated comment block; added TODO for
  `"Join"` and `"Remove"`.
- `test/adapters/driving/fastapi/test_outbox.py`: Added 6 new parametrized
  tests (3 expansion-success + 3 integrity-error-on-failure) covering
  `Add`, `Invite`, `Accept`; moved top-level imports (`pytest`,
  `VultronOutboxObjectIntegrityError`); added `_make_activity_with_bare_object`
  helper.

### Test Result

1625 passed, 12 skipped, 182 deselected, 5581 subtests passed

---

## P347-SUGGESTBT — SuggestActorToCase BT Handler

**Completed**: P347-SUGGESTBT

### Summary

Replaced the stub `SuggestActorToCaseReceivedUseCase.execute()` with a proper
behavior tree that enforces case-ownership preconditions, idempotency, and
outbox emission.

### New File

- `vultron/core/behaviors/case/suggest_actor_tree.py` — 4 BT nodes and factory:
  - `CheckIsCaseOwnerNode`: reads case from DataLayer, compares
    `case.attributed_to` to `actor_id`; returns FAILURE to silently skip if
    not owner.
  - `CheckNoExistingInviteNode`: uses a deterministic UUID-v5 invite ID to
    check for duplicate invite; returns FAILURE to skip if already sent.
  - `EmitAcceptRecommendationNode`: creates and queues
    `AcceptActorRecommendationActivity` (with full inline
    `RecommendActorActivity` as required `object_`).
  - `EmitInviteToCaseNode`: creates and queues `RmInviteToCaseActivity` with
    the same deterministic ID used by the idempotency check.
  - `create_suggest_actor_tree()`: factory returning the Sequence.

### Updated File

- `vultron/core/use_cases/received/actor.py` —
  `SuggestActorToCaseReceivedUseCase.execute()` now:
  1. Persists incoming recommendation via `_idempotent_create`.
  2. Finds local actor via `_find_local_actor_id`.
  3. Builds the BT via `create_suggest_actor_tree()`.
  4. Runs via `BTBridge.execute_with_setup()`.

### Tests Added

- `test/core/use_cases/received/test_actor.py` — merged into existing
  `TestSuggestActorUseCases`:
  - `test_suggest_actor_emits_both_activities_when_owner`
  - `test_suggest_actor_skips_when_not_case_owner`
  - `test_suggest_actor_idempotent_when_invite_exists`

### Test Result

1628 passed, 12 skipped, 182 deselected, 5581 subtests passed

## P347-TRIGGERS — New Trigger Endpoints (create-case, add-report-to-case, suggest-actor-to-case, accept-case-invite)

**Completed:** P347-TRIGGERS from PRIORITY-347 (Demo Puppeteering, Trigger Completeness, BT Generalization)

### Summary

Added four new trigger endpoints that allow actors to initiate case-related
protocol actions without requiring direct inbox injection (enabling
puppeteering over spoofing in demos).

### Changes

**New domain request models** (`vultron/core/use_cases/triggers/requests.py`):

- `CreateCaseTriggerRequest` — `actor_id`, `name`, `content`, `report_id?`
- `AddReportToCaseTriggerRequest` — `actor_id`, `case_id`, `report_id`
- `SuggestActorToCaseTriggerRequest` — `actor_id`, `case_id`, `suggested_actor_id`
- `AcceptCaseInviteTriggerRequest` — `actor_id`, `invite_id`

**New HTTP request body models** (`vultron/adapters/driving/fastapi/trigger_models.py`):

- `CreateCaseRequest`, `AddReportToCaseRequest`, `SuggestActorToCaseRequest`, `AcceptCaseInviteRequest`

**New use cases** (`vultron/core/use_cases/triggers/case.py`):

- `SvcCreateCaseUseCase` — creates `VulnerabilityCase` + `CreateCaseActivity` → outbox
- `SvcAddReportToCaseUseCase` — creates `AddReportToCaseActivity` → outbox

**New use cases** (`vultron/core/use_cases/triggers/actor.py`, new file):

- `SvcSuggestActorToCaseUseCase` — creates `RecommendActorActivity` → outbox
- `SvcAcceptCaseInviteUseCase` — reads invite, coerces to `RmInviteToCaseActivity`, creates `RmAcceptInviteToCaseActivity` → outbox

**New adapter functions** (`vultron/adapters/driving/fastapi/_trigger_adapter.py`):

- `create_case_trigger`, `add_report_to_case_trigger`, `suggest_actor_to_case_trigger`, `accept_case_invite_trigger`

**Router updates**:

- `trigger_case.py` — added `POST /{actor_id}/trigger/create-case` and `POST /{actor_id}/trigger/add-report-to-case`
- `trigger_actor.py` — new file with `POST /{actor_id}/trigger/suggest-actor-to-case` and `POST /{actor_id}/trigger/accept-case-invite`
- `v2_router.py` — registered `trigger_actor.router`

**Tests**:

- `test_trigger_case.py` — added 13 tests for create-case and add-report-to-case
- `test_trigger_actor.py` — new file with 13 tests for suggest-actor-to-case and accept-case-invite

### Test Result

1652 passed, 12 skipped, 182 deselected, 5581 subtests passed

---

## P347-EMBARGOTRIGGERS — Embargo Trigger Rename + Accept/Reject/Revision

### Task

Rename `evaluate-embargo` trigger endpoint → `accept-embargo`, add
`reject-embargo` and `propose-embargo-revision` trigger endpoints across all
layers (core use cases, FastAPI router, MCP server, tests, specs).

### Changes

**Core layer:**

- `vultron/core/use_cases/triggers/requests.py`: Renamed
  `EvaluateEmbargoTriggerRequest` → `AcceptEmbargoTriggerRequest`; added
  `RejectEmbargoTriggerRequest` and `ProposeEmbargoRevisionTriggerRequest`;
  backward-compat alias preserved.
- `vultron/core/use_cases/triggers/embargo.py`: Renamed
  `SvcEvaluateEmbargoUseCase` → `SvcAcceptEmbargoUseCase`; added
  `SvcRejectEmbargoUseCase` (PROPOSED→NO_EMBARGO / REVISE→ACTIVE EM
  transition, emits `EmRejectEmbargoActivity`); added
  `SvcProposeEmbargoRevisionUseCase` (ACTIVE/REVISE only, PROPOSE EM
  transition, emits `EmProposeEmbargoActivity`); backward-compat alias
  preserved.

**Adapter layer:**

- `vultron/adapters/driving/fastapi/trigger_models.py`: Renamed
  `EvaluateEmbargoRequest` → `AcceptEmbargoRequest`; added
  `RejectEmbargoRequest` and `ProposeEmbargoRevisionRequest`.
- `vultron/adapters/driving/fastapi/_trigger_adapter.py`: Renamed
  `evaluate_embargo_trigger` → `accept_embargo_trigger`; added
  `reject_embargo_trigger` and `propose_embargo_revision_trigger`.
- `vultron/adapters/driving/fastapi/routers/trigger_embargo.py`: Renamed
  `evaluate-embargo` → `accept-embargo` endpoint; added `reject-embargo` and
  `propose-embargo-revision` endpoints.
- `vultron/adapters/driving/mcp_server.py`: Renamed `mcp_evaluate_embargo` →
  `mcp_accept_embargo`; added `mcp_reject_embargo` and
  `mcp_propose_embargo_revision`; updated `MCP_TOOLS` list.

**Tests:**

- `test/adapters/driving/fastapi/routers/test_trigger_embargo.py`: Renamed
  all `evaluate-embargo` URL references to `accept-embargo`; added ~20 new
  tests for `reject-embargo` and `propose-embargo-revision` endpoints.
- `test/core/use_cases/received/test_embargo.py`: Updated imports.
- `test/core/use_cases/triggers/test_trignotify.py`: Updated imports.

**Specs:**

- `specs/triggerable-behaviors.md`: Updated `TRIG-02-002` table to show
  `accept-embargo`, `reject-embargo`, and `propose-embargo-revision`; updated
  `TRIG-03-001` case-scoped behaviors list.

### Test Result

1669 passed, 12 skipped, 182 deselected, 5581 subtests passed

---

## P347-DEMOORG — Reorganize demo/ into exchange/ and scenario/ sub-packages

**Commit**: d4e650e5
**Priority**: 347

Reorganized `vultron/demo/` into two semantically distinct sub-packages:

- **`vultron/demo/exchange/`** (13 scripts): Individual protocol-fragment demos
  using direct inbox injection to demonstrate single-message semantics.
  (`receive_report_demo`, `initialize_case_demo`, `initialize_participant_demo`,
  `invite_actor_demo`, `establish_embargo_demo`, `acknowledge_demo`,
  `status_updates_demo`, `suggest_actor_demo`, `transfer_ownership_demo`,
  `manage_case_demo`, `manage_embargo_demo`, `manage_participants_demo`,
  `trigger_demo`)

- **`vultron/demo/scenario/`** (3 scripts): End-to-end multi-actor workflow demos
  using trigger-based puppeteering.
  (`two_actor_demo`, `three_actor_demo`, `multi_vendor_demo`)

**Changes:**

- Created `exchange/__init__.py` and `scenario/__init__.py` with docstrings
- `git mv` all 16 demo scripts into the appropriate sub-package
- Updated cross-imports in `three_actor_demo.py` and `multi_vendor_demo.py`
- Updated all 16 import paths in `vultron/demo/cli.py`
- Updated all import paths in 18 test files under `test/demo/`
- Updated mkdocstrings references in `docs/reference/code/demo/demos.md`
- Added `exchange/README.md` and `scenario/README.md`
- Restructured `vultron/demo/README.md` to describe the two sub-packages

**Test Result:**

1669 passed, 12 skipped, 182 deselected, 5581 subtests passed

---

## P347-PUPPETEER — Demo Trigger-Based Puppeteering (COMPLETE 2026-07-21)

**Task:** Convert all spoofing functions in `three_actor_demo.py` and
`multi_vendor_demo.py` from direct inbox injection to trigger-based
puppeteering. Added inline prerequisite: `invite-actor-to-case` trigger.

**New trigger added (inline prerequisite):**

- `InviteActorToCaseTriggerRequest` in `requests.py`
- `SvcInviteActorToCaseUseCase` in `triggers/actor.py`
- `InviteActorToCaseRequest` HTTP model in `trigger_models.py`
- `invite_actor_to_case_trigger` adapter in `_trigger_adapter.py`
- `POST /{actor_id}/trigger/invite-actor-to-case` endpoint in `trigger_actor.py`

**Spoofing functions converted (5 in three_actor_demo.py):**

- `coordinator_creates_case_on_case_actor` — now calls `create-case` trigger,
  adds `coordinator_client` param
- `coordinator_adds_report_to_case` — now calls `add-report-to-case` trigger,
  adds `coordinator_client` param
- `coordinator_invites_actor` — fully redesigned: new signature
  `(actor_client, recipient_client, actor, recipient, case, case_actor_client=None,
  case_actor=None)`, calls `invite-actor-to-case` trigger
- `actor_accepts_case_invite` — now calls `accept-case-invite` trigger, adds
  `actor_client` param, delivers accept to case_actor
- `actor_accepts_embargo` — now calls `accept-embargo` trigger on
  `case_actor_client`, removes `case_actor` param and `EmAcceptEmbargoActivity`
  return type

**Spoofing functions converted (2 in multi_vendor_demo.py):**

- `vendor_creates_case_on_case_actor` — now calls `create-case` trigger,
  adds `vendor_client` param
- `vendor_adds_report_to_case` — now calls `add-report-to-case` trigger,
  adds `vendor_client` param

**Test updates:**

- `test/demo/test_three_actor_demo.py` — updated call site for
  `coordinator_creates_case_on_case_actor`; removed stale assertion that case
  was NOT in coordinator's DL (now it IS, by design)
- `test/demo/test_multi_vendor_demo.py` — updated both call sites for
  `vendor_creates_case_on_case_actor`; attribution now checked against
  `vendor_in_vendor.id_`
- `test/core/use_cases/triggers/test_actor_triggers.py` — new: 4 unit tests
  for `SvcInviteActorToCaseUseCase`

**Test Result:**

1673 passed, 12 skipped, 182 deselected, 5581 subtests passed

---

## 2026-04-20 — DR-03 / DR-04: Semantic extraction fix and fail-fast validation

**Tasks completed:** DR-03 (High), DR-04 (High)

**Summary:**

Fixed two bugs from the 2026-04-20 demo review that caused inbox crash-loops
when unresolved ActivityStreams references (bare string IDs) were received.

### DR-03 — _match_field() ordering fix in ActivityPattern.match()

**Root cause:** `_match_field()` in `ActivityPattern.match()` checked
`isinstance(activity_field, str)` (conservative allow) BEFORE checking
`isinstance(pattern_field, ActivityPattern)` (nested pattern check). This
caused `Accept("bare-string-id")` to satisfy nested-activity pattern
constraints (e.g., `ReportSubmissionPattern`), causing `Accept(bare_string)`
to be classified as `VALIDATE_REPORT`, triggering a downstream `ValueError`
and inbox retry loop.

**Fix:** Moved the `isinstance(pattern_field, ActivityPattern)` check BEFORE
the string passthrough in `_match_field()`. Bare string `object_` values now
return `False` when the pattern requires a nested typed activity (instead of
`True`), causing those activities to dispatch as `UNKNOWN` (which just logs
a warning and returns cleanly).

**Files changed:**

- `vultron/wire/as2/extractor.py` — reordered `_match_field()` checks
- `test/test_semantic_activity_patterns.py` — new test:
  `test_accept_with_bare_string_object_returns_unknown`

### DR-04 — Fail-fast validation for ValidateReportReceivedEvent

Added `@model_validator(mode='after')` to `ValidateReportReceivedEvent` to
raise `ValueError` at construction time when `offer_id` or `report_id` is
`None`. Previously the check was only inside `execute()` as a bare
`ValueError`. Updated the residual check in
`ValidateReportReceivedUseCase.execute()` to raise `VultronValidationError`
(domain error) instead of bare `ValueError`.

**Files changed:**

- `vultron/core/models/events/report.py` — added `model_validator` to
  `ValidateReportReceivedEvent`
- `vultron/core/use_cases/received/report.py` — imported and used
  `VultronValidationError` instead of bare `ValueError`

### DR-07 — AnnounceLogEntryActivity immediate fix

Already complete in a prior commit (`AnnounceLogEntryPattern` already has
`object_=VOtype.CASE_LOG_ENTRY`). The `InviteActorToCasePattern` sub-issue
(add `object_=AOtype.ACTOR`) was attempted but reverted: `AOtype.ACTOR`
only matches `type_="Actor"` (the base AS2 Actor class), while real invite
activities use actor subtypes (`Person`, `Organization`, `Service`) which
have `type_!="Actor"`. The pattern would need subtype-aware matching to
implement correctly. Noted in IMPLEMENTATION_NOTES.md for DR-07 audit.

**Test Result:**

1674 passed, 12 skipped, 182 deselected, 5581 subtests passed

---

## PRIORITY-348 DR-01 + DR-02 — Outbox reference dehydration and activity name fix

**Date:** 2026-04-20

### DR-01 — Outbox reference-field dehydration

**Problem:** `handle_outbox_item()` in `outbox_handler.py` converts typed AS2
activities (e.g. `RmInviteToCaseActivity`) to `VultronActivity` via
`model_dump(by_alias=True)` + `VultronActivity.model_validate()`. Trigger
use cases may set reference fields (e.g. `target`) to full domain objects
(e.g. a `VulnerabilityCase`). Since `VultronActivity.target: NonEmptyString | None`,
validation failed with a type error.

**Fix:** Added `_dehydrate_references(activity_dict: dict) -> dict` to
`outbox_handler.py`. Collapses dict-valued reference fields to URI strings
by preferring `href` (AS2 Link) then `id`. Handles list fields element-wise.
Fields dehydrated: `actor`, `target`, `to`, `cc`, `bto`, `bcc`, `origin`,
`result`, `instrument`. `"object"` is explicitly exempt (must stay inline).
Applied to the raw `model_dump()` dict before `VultronActivity.model_validate()`.

### DR-02 — Activity `name` repr bug

**Problem:** `as_TransitiveActivity.set_name()` constructed the activity `name`
using `str(self.target)` etc., which produced Python Pydantic repr strings
(e.g. `"type_=<VultronObjectType.VULNERABILITY_CASE: 'VulnerabilityCase'>..."`)
for domain objects. Also, `name_of()` returned the string `"None"` when
`obj.name` was `None`, rather than falling back to a meaningful ID.

**Fix (two parts):**

1. Updated `name_of()` in `vultron/wire/as2/vocab/base/utils.py`:
   now returns strings directly, falls back to `href` (links), then `id_`,
   then `str(obj)`. Never returns `"None"` for objects with `id_`.
2. Applied `name_of()` consistently in `as_TransitiveActivity.set_name()`
   for `origin`, `target`, and `instrument` fields (was using raw `str()`
   conversion before).

**Files changed:**

- `vultron/adapters/driving/fastapi/outbox_handler.py`: `_dehydrate_references()` + application
- `vultron/wire/as2/vocab/base/utils.py`: updated `name_of()`
- `vultron/wire/as2/vocab/base/objects/activities/transitive.py`: `set_name()` fix
- `test/adapters/driving/fastapi/test_outbox.py`: regression + unit tests for DR-01
- `test/wire/as2/vocab/test_base_utils.py`: tests for `name_of()` and `set_name()`

**Test Result:**

1689 passed, 12 skipped, 182 deselected, 5581 subtests passed

---

## DR-08, DR-11, DR-12 — Note BT, PersistCase upsert, get_failure_reason

**Completed:** DR-08, DR-11, DR-12 (PRIORITY-348 batch)

### DR-08 — `create_note`: AttachNoteToCaseNode BT node

Implemented a full note BT package at `vultron/core/behaviors/note/`:

- `nodes.py`: `SaveNoteNode` (upsert via `dl.save()`) and `AttachNoteToCaseNode`
  (idempotent append of `note_id` to `case.notes`; returns SUCCESS immediately
  when `case_id` is None — standalone notes are valid).
- `create_note_tree.py`: `create_note_tree(note_obj, case_id)` factory returning
  a `Sequence` of `[SaveNoteNode, AttachNoteToCaseNode]`.
- `CreateNoteReceivedUseCase.execute()` rewired to use `BTBridge` +
  `create_note_tree()`; removed `_idempotent_create` usage.
- Key detail: `case_id` comes from `event.note.context` (the Note object's
  context field), not `event.context_id`.

### DR-11 — PersistCase: upsert semantics

Changed `PersistCase.update()` in `vultron/core/behaviors/case/nodes.py` to
call `dl.save()` (upsert) instead of `dl.create()` + `except ValueError`. The
node is now truly idempotent with no warning on duplicate case creation.

### DR-12 — `get_failure_reason(tree)` helper

Added `BTBridge.get_failure_reason(tree)` static method to
`vultron/core/behaviors/bridge.py`. Algorithm: depth-first walk of the tree,
skipping composite nodes (nodes with children), returning the first failing
leaf's `feedback_message` or class name. Returns `""` if no failure is found.
Used in `CreateNoteReceivedUseCase` failure logging.

**Files created:**

- `vultron/core/behaviors/note/__init__.py`
- `vultron/core/behaviors/note/nodes.py`
- `vultron/core/behaviors/note/create_note_tree.py`
- `test/core/behaviors/note/__init__.py`
- `test/core/behaviors/note/conftest.py`
- `test/core/behaviors/note/test_create_note_tree.py` (14 tests)

**Files modified:**

- `vultron/core/behaviors/bridge.py` — added `get_failure_reason`
- `vultron/core/behaviors/case/nodes.py` — `PersistCase` uses `dl.save()`
- `vultron/core/use_cases/received/note.py` — BT-driven execution
- `test/core/behaviors/test_bridge.py` — 4 new `get_failure_reason` tests
- `test/core/use_cases/received/test_note.py` — 2 new attachment tests

**Test Result:**

1706 passed, 12 skipped, 182 deselected, 5581 subtests passed

---

## PRIORITY-348 DR-07 — ActivityPattern actor subtype-aware matching

**Completed:** 2026-05-05

**Task:** DR-07 — ActivityPattern discrimination requirement (remaining work).

**Problem:** `InviteActorToCasePattern` had no `object_` discriminator, violating
SE-03-003. The `_match_field()` function used exact `type_` string equality, but
real AS2 actor subtypes (`Person`, `Organization`, `Service`) have different
`type_` values than the base `Actor`. Adding `object_=AOtype.ACTOR` would fail
to match real invites because `"Person" != "Actor"`.

**Solution:**

1. Added subtype-aware matching in `_match_field()` (in `ActivityPattern.match()`
   in `vultron/wire/as2/extractor.py`): when `pattern_field == AOtype.ACTOR`,
   check `isinstance(activity_field, as_Actor)` rather than comparing `type_`
   strings. This matches all actor subtypes correctly.
2. Added `object_=AOtype.ACTOR` discriminator to `InviteActorToCasePattern`.
   This propagates through `AcceptInviteActorToCasePattern` and
   `RejectInviteActorToCasePattern` (which use nested patterns).
3. Added import of `as_Actor` from `vultron.wire.as2.vocab.base.objects.actors`.

**Files changed:**

- `vultron/wire/as2/extractor.py` — subtype-aware `_match_field()`, new import,
  `object_=AOtype.ACTOR` on `InviteActorToCasePattern`
- `test/test_semantic_activity_patterns.py` — 9 new tests (4×Person/Org/Svc/Actor
  for Invite, 4×Accept(Invite), 1×non-actor object doesn't match)

**Test Result:**

1715 passed, 12 skipped, 182 deselected, 5581 subtests passed

---

## DR-13 — `SubmitReportReceivedUseCase`: Remove vendor/target assumptions (COMPLETE)

**Task**: Refactor `SubmitReportReceivedUseCase` to use `Offer.to` (not
`Offer.target`) as the signal for identifying the receiving actor and
determining whether to create a case. Per HP-09-001 and HP-09-002.

**Changes:**

1. `vultron/core/models/events/base.py` — Added `receiving_actor_id: str | None
   = None` to `VultronEvent`. This dispatch-context annotation holds the
   canonical ID of the actor whose inbox is being processed (set by the inbox
   adapter, not extracted from wire format).

2. `vultron/wire/as2/extractor.py` — Added `_get_id_list()` helper that converts
   AS2 `to`/`cc` fields (`Any | None`) to `list[str] | None`. Now copies `to`
   and `cc` into the `VultronActivity` when building domain kwargs for
   `_ACTIVITY_SEMANTICS` message types.

3. `vultron/adapters/driving/fastapi/inbox_handler.py` — Two changes:
   - `handle_inbox_item`: injects `receiving_actor_id` into the event via
     `model_copy(update={"receiving_actor_id": actor_id})` after
     `prepare_for_dispatch`.
   - `inbox_handler`: normalizes `actor_id` to canonical URI via
     `getattr(actor, "id_", None) or actor_id` before calling
     `handle_inbox_item` (so that it matches `activity.to`/`cc` field values).

4. `vultron/core/use_cases/received/report.py` — Replaced
   `vendor_actor_id = request.target_id` with:
   - Reads `receiving_actor_id` from `request.receiving_actor_id`
   - Reads `to_list`/`cc_list` from `request.activity.to`/`.cc`
   - If `receiving_actor_id` is in `to_list` → proceed to case creation
   - If in `cc_list` → log WARNING "cc addressing not supported", discard
   - Otherwise → log WARNING "receiving actor in neither to nor cc", discard
   - BT execution now uses `receiving_actor_id` (was `vendor_actor_id`)

5. `test/core/use_cases/received/test_report.py` — Updated all
   `SubmitReportReceivedEvent` constructions to use `to=[vendor_id]` and
   `receiving_actor_id=vendor_id` instead of `target=vendor_id`. Added new
   `TestOfferAddressingSemantics` class with 5 tests covering HP-09-001/HP-09-002
   verification criteria (in-to, in-cc, in-neither, target-not-consulted,
   inverse-target-check).

6. `test/adapters/driving/fastapi/test_inbox_handler.py` — Updated
   `test_handle_inbox_item_dispatches` to use a real `VultronEvent` instead of
   `SimpleNamespace` (required by the new `model_copy` call in `handle_inbox_item`).
   Added assertion that `dispatched_event.receiving_actor_id` is set correctly.

**Key design decision**: `receiving_actor_id` is a dispatch-context annotation
added by the inbox adapter — not a wire-format concept. It defaults to `None`
for backward compatibility with non-inbox dispatch paths (CLI, triggers, tests).

**Test Result:**

1720 passed, 12 skipped, 182 deselected, 5581 subtests passed

---

## IDEA-26041501: Consolidated Semantic Dispatch Registry

**Commit:** bee96bb3
**Branch:** d5

Replaced four separate dispatch dictionaries (`SEMANTICS_ACTIVITY_PATTERNS`,
`EVENT_CLASS_MAP`, `USE_CASE_MAP`, `SEMANTICS_TO_ACTIVITY_CLASS`) with a
single `SEMANTIC_REGISTRY` list of frozen `SemanticEntry` dataclasses in
`vultron/semantic_registry.py`. Per CS-13-001, no backward-compatibility
aliases were added — all four dicts were deleted and all callers updated.

Key changes:

- `vultron/semantic_registry.py` — new neutral module; single source of truth
  for pattern→semantics→event-class→use-case-class→wire-activity-class mapping
- `extractor.py` — stripped wire activity-class imports; `extract_intent()`
  signature now takes explicit params; `_PATTERN_SEMANTICS` replaces public dict
- `vultron/core/use_cases/use_case_map.py` — deleted
- `vultron/core/models/events/__init__.py` — `EVENT_CLASS_MAP` deleted
- `specs/code-style.md` — CS-13-001 No Compatibility Shims added
- `test/test_semantic_registry.py` — new completeness/consistency tests

**Test Result:**

1729 passed, 12 skipped, 182 deselected, 5581 subtests passed

---

## P347-SPECS — Spec and Notes Updates for Trigger Completeness (COMPLETE 2026-04-21)

Updated three documentation files to reflect the full set of trigger endpoints
implemented in PRIORITY-347:

- `specs/triggerable-behaviors.md`: Added TRIG-02-004 (Case Management
  Behaviors: `create-case`, `add-report-to-case`, `add-note-to-case`,
  `submit-report`) and TRIG-02-005 (Participant Management Behaviors:
  `suggest-actor-to-case`, `invite-actor-to-case`, `accept-case-invite`).
  Updated TRIG-03-001 request body requirements to include the new behaviors
  and added an `invite_id` requirement for `accept-case-invite`. Expanded
  TRIG-02-003 Verification to cover the new requirement IDs.

- `specs/multi-actor-demo.md`: Added DEMO-MA-05-001 and DEMO-MA-05-002
  requiring that all actor-initiated actions in scenario demos MUST be driven
  through the trigger API, not by direct inbox injection.

- `notes/protocol-event-cascades.md`: Added a concrete 4-step
  suggest→invite→accept→record cascade example (with implementation
  requirements referencing TRIG-02-005 and DEMO-MA-05-001).

---

## DR-06 — Per-participant embargo consent state machine

**Completed:** PRIORITY-348 / DR-06 (High)

### Summary

Implemented a 5-state `PEC` (Participant Embargo Consent) machine to track
each case participant's individual consent status independently of the shared
case-level `EM` state machine.

### Files Created

- `vultron/core/states/participant_embargo_consent.py` — `PEC` enum, `PEC_Trigger`
  enum, `PECAdapter`, `create_pec_machine()`, and `apply_pec_trigger()` helper.
- `test/core/states/__init__.py` and `test/core/states/test_participant_embargo_consent.py` —
  tests for all valid and invalid PEC transitions.

### Files Modified

- `vultron/core/models/participant.py` — Added `embargo_consent_state: PEC` field.
- `vultron/wire/as2/vocab/objects/case_participant.py` — Added `embargo_consent_state: str`
  wire field.
- `vultron/core/models/protocols.py` — Added `embargo_consent_state: str` to `ParticipantModel`.
- `vultron/core/use_cases/received/embargo.py`:
  - `InviteToEmbargoOnCaseReceivedUseCase`: sets participant consent to `INVITED`.
  - `AcceptInviteToEmbargoOnCaseReceivedUseCase`: case-owner gate — only the
    `attributed_to` actor activates shared EM; non-owners update own consent
    only. Sets participant consent to `SIGNATORY`.
  - `RejectInviteToEmbargoOnCaseReceivedUseCase`: sets participant consent to
    `DECLINED`, extracts case/embargo IDs from stored invite activity.
  - `RemoveEmbargoEventFromCaseReceivedUseCase`: resets all participants to
    `NO_EMBARGO` when active embargo is removed.
- `vultron/core/use_cases/received/actor.py`:
  - `AcceptInviteActorToCaseReceivedUseCase`: auto-sign embargo consent
    (`SIGNATORY`) only when `em_state == EM.ACTIVE` (not when REVISE).
- `vultron/core/use_cases/triggers/embargo.py`:
  - Added `_cascade_pec_revise()` and `_cascade_pec_reset()` helpers.
  - `SvcAcceptEmbargoUseCase`: sets local actor's participant to `SIGNATORY`.
  - `SvcProposeEmbargoUseCase`: cascades `REVISE` trigger on `ACTIVE → REVISE`
    transition (all signatories lapse).
  - `SvcTerminateEmbargoUseCase`: cascades `RESET` before saving case.
- `test/core/use_cases/received/test_embargo.py` — Updated 3 tests to set
  `attributed_to` on the case, matching the case-owner gate requirement.
- `test/core/use_cases/received/test_actor.py` — Updated 1 test to set
  `em_state = EM.ACTIVE` when `active_embargo` is present, matching the guard.

### Notes

- Timer-based pocket-veto (`INVITED`/`LAPSED → DECLINED` after
  `embargo_invitation_timeout`) is a policy concern left for a future task.
- The `embargo_adherence: bool` derived property (returns `state == SIGNATORY`)
  was not added; deferred — no spec requiring it was blocked on this.

---

## SYNC-4 — Multi-peer synchronization with per-peer replication state

**Status**: Complete (discovered already implemented; plan updated)
**Priority**: 330
**Completed**: 2026-04-21
**Commits**: `25babfd6` (implemented as part of SYNC-3 changeset)

### Summary

SYNC-4 was fully implemented in commit `25babfd6` alongside SYNC-3. The
plan entry was not removed at the time. Verification confirmed all
components present:

- `VultronReplicationState` model (`vultron/core/models/replication_state.py`)
- `_update_replication_state()` in `vultron/core/use_cases/received/sync.py`
- BT leadership guard (`is_leader` parameter on `BTBridge.__init__()`)
- Tests: `test/core/use_cases/received/test_reject_sync.py` (SYNC-04-001/002)

No code changes required; removed stale plan entry.

---

## DR-05 — Accept.object_ must carry the original Invite

**Status**: Complete (bug already fixed; regression tests added)
**Priority**: 348
**Completed**: 2026-04-21
**Commits**: `e27bb4ef` (accept-case-invite trigger), `001b1cc4` (INLINE-OBJ-B),
`1dff5fab` (P347-PUPPETEER); regression tests in this session.

### Summary

The DR-05 bug (Accept.object_ set to VulnerabilityCase instead of the
original invite) was introduced by old demo puppeteering scripts and fixed
on 2026-04-20 via three coordinated changes:

1. `e27bb4ef` — Added `accept-case-invite` trigger
   (`SvcAcceptCaseInviteUseCase`), which reads the invite from the DataLayer
   and passes it as `object_=invite` to `RmAcceptInviteToCaseActivity`.
2. `001b1cc4` (INLINE-OBJ-B) — Pydantic enforces `object_:
   RmInviteToCaseActivity` (required) on all Accept/Reject invite activities,
   and `object_: EmProposeEmbargoActivity` on embargo Accept/Reject.
3. `1dff5fab` (P347-PUPPETEER) — Demo scripts migrated to trigger-based
   approach; old puppeteering code removed.

`SvcAcceptEmbargoUseCase` (embargo.py) was similarly correct.

This session added two regression tests:

- `test_trigger_accept_case_invite_object_is_invite` — verifies
  `activity.object.id == invite.id_` (RM path)
- `test_trigger_accept_embargo_object_is_proposal` — verifies
  `activity.object.id == proposal.id_` (EM path)

### Notes

The IMPLEMENTATION_NOTES design described a "BT blackboard stash" approach
as the intended fix. The actual fix used the trigger + DataLayer lookup
pattern instead. The BT-blackboard description in NOTES is superseded and
was not implemented; trigger-based DL lookup is the canonical pattern.

---

## DR-14 — Dead-letter handling for unresolvable `object_` URIs (COMPLETE 2026-05-01)

**Reference**: `specs/semantic-extraction.md` SE-04-002–SE-04-004

### What was implemented

Introduced a new `MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT` enum value and
a full pipeline for activities that match a known AS2 type but whose `object_`
field remains a bare string URI after rehydration (i.e., cannot be resolved
from the DataLayer).

Key changes:

1. **`vultron/core/models/events/base.py`** — Added `UNKNOWN_UNRESOLVABLE_OBJECT`
   enum value after `UNKNOWN`.

2. **`vultron/wire/as2/extractor.py`** — Added `_ACTIVITY_TYPES_WITH_PATTERNS`
   frozenset (computed from `_PATTERN_SEMANTICS`); updated `find_matching_semantics()`
   to return `UNKNOWN_UNRESOLVABLE_OBJECT` when: no pattern matched AND `object_`
   is still a bare string AND the activity type is registered in known patterns.
   Truly unrecognized activity types continue to fall through to `UNKNOWN`.

3. **`vultron/core/models/events/unknown.py`** — Added `UnresolvableObjectReceivedEvent`
   with required (narrowed) `activity: VultronActivity` field.

4. **`vultron/core/models/dead_letter.py`** (new) — `DeadLetterRecord` domain
   model for dead-letter storage with fields: `type_`, `unresolvable_uri`,
   `actor_id`, `activity_id`, `activity_type`, `activity_summary`, `received_at`.

5. **`vultron/core/use_cases/received/unknown.py`** — Added `UnresolvableObjectUseCase`
   that logs a WARNING and calls `dl.save(DeadLetterRecord(...))`.

6. **`vultron/semantic_registry.py`** — Added `SemanticEntry` for
   `UNKNOWN_UNRESOLVABLE_OBJECT` (with `include_activity=True`, `pattern=None`)
   as the second-to-last entry, before the `UNKNOWN` fallback.

7. **Tests** — Updated two registry tests to use a sentinel set excluding both
   UNKNOWN variants. Added `test_registry_unresolvable_object_is_second_to_last`.
   Updated `test_semantic_activity_patterns.py` with renamed bare-string test
   and new unregistered-type test. Added new
   `test/core/use_cases/received/test_unresolvable_object.py` (7 tests).

### Commits

- see git log (DR-14 commit)

### Notes

- `DeadLetterRecord` does NOT require vocabulary registration; `dl.by_type()`
  queries the `type_` column directly, so no `record_to_object()` call needed.
- `by_type()` returns raw data dicts (without the `type_` column), so tests
  check for presence of field values rather than `type_` key.
- `UnresolvableObjectReceivedEvent.activity` narrows the optional base field to
  required; a file-level `# pyright: reportGeneralTypeIssues=false` directive
  suppresses the pyright inheritance warning (documented pattern).

---

## DR-09 — Actor ID normalization (PRIORITY-348)

**Completed:** 2026-04-21

**Task:** Normalize actor IDs to full URIs everywhere internally so that
`add_activity_to_outbox` and related functions never receive a short UUID.

**Root cause:** Three trigger use cases in
`vultron/core/use_cases/triggers/actor.py` — `SvcSuggestActorToCaseUseCase`,
`SvcInviteActorToCaseUseCase`, and `SvcAcceptCaseInviteUseCase` — called
`resolve_actor(actor_id, dl)` to look up the actor but never reassigned
`actor_id = actor.id_`. As a result, `add_activity_to_outbox(actor_id, ...)` was
called with the raw short UUID from the HTTP URL path, causing a DataLayer lookup
failure and the warning logged in the demo review.

**Fix:** Added `actor_id = actor.id_` immediately after each `resolve_actor()`
call in all three use cases. Replaced redundant `actor.id_` references in
activity constructors with the now-canonical `actor_id`.

**Tests added:**

- `test/core/use_cases/triggers/test_actor_triggers.py` extended with:
  - `TestSvcInviteActorToCaseUseCase.test_invite_normalises_short_uuid_actor_id`
  - `TestSvcSuggestActorToCaseUseCase` (new class: 2 tests)
  - `TestSvcAcceptCaseInviteUseCase` (new class: 3 tests)

All 1770 unit tests pass; all four linters (black, flake8, mypy, pyright) clean.

**Lessons learned:**

- All other trigger use case files (embargo.py, case.py, report.py, note.py)
  already had the correct `actor_id = actor.id_` reassignment pattern.
- The FastAPI trigger routers pass the raw URL path `actor_id` to use-case
  requests; the `_canonical_actor_dl` dependency only normalizes the DataLayer
  scoping, not the actor_id string passed in the request body.

---

## DR-10 — Stub objects for Invite.target selective disclosure

**Completed:** 2026-04-21

**Task:** Implement selective disclosure for case invites so `Invite.target`
uses a `VulnerabilityCase` stub before acceptance, then deliver the full case
object after the invitee accepts.

**What was done:**

- Added `VulnerabilityCaseStub` and narrowed `RmInviteToCaseActivity.target`
  so invite flows now disclose only `{id, type}` plus optional `summary`.
- Added `ANNOUNCE_VULNERABILITY_CASE` across the semantic pipeline:
  `MessageSemantics`, extractor pattern registration, event model, semantic
  registry wiring, and `AnnounceVulnerabilityCaseActivity`.
- Updated invite acceptance handling to emit
  `AnnounceVulnerabilityCaseActivity` with the full case object after
  acceptance so the invitee can seed a local case copy.
- Added `AnnounceVulnerabilityCaseReceivedUseCase` to create the case
  idempotently on the recipient side and skip malformed/non-case payloads.
- Tightened outbox dehydration so only `VulnerabilityCase` stubs are preserved
  as stub objects; unrelated minimal objects like actors still collapse to IDs.
- Added regression coverage for selective-disclosure serialization, invite
  typing, semantic pattern routing, announce receive-side seeding, and the new
  outbox behavior.

**Validation:**

- `uv run flake8 vultron/ test/`
- `uv run mypy`
- `uv run pyright`
- `uv run pytest --tb=short 2>&1 | tail -5`
- Final unit summary:
  `1779 passed, 12 skipped, 182 deselected, 5581 subtests passed`

**Lessons learned:**

- `event.activity` cannot be collapsed to ID strings when a receive-side use
  case needs the full inline payload; DR-10 required preserving rich
  `object_` / `target` / `context` values on the included activity snapshot.
- `VulnerabilityCaseStub` had to override the inherited `published` and
  `updated` defaults from `as_Object`; otherwise timestamp fields leaked into
  the serialized stub and broke the selective-disclosure contract.

---

## BUG-26041701 — outbound initiating bare-string `object_` bug closure (COMPLETE 2026-04-22)

**Issue:** `plan/BUGS.md` tracked multi-party demo failures where outbound
initiating activities appeared to carry bare-string or Link `object_` values,
triggering MV-09-001 outbox integrity errors.

**Root cause:** The bug entry was still open after the underlying INLINE-OBJ
and outbox integrity work had already landed. Current code now emits typed
inline objects in the case-participant Add path, activity classes reject bare
string/Link `object_` payloads at construction time, and the outbox handler
enforces/bridges legacy bare-string cases before delivery.

**Resolution:** Verified the fix in the current tree, confirmed the relevant
regression tests pass, and marked BUG-26041701 fixed without additional code
changes.
