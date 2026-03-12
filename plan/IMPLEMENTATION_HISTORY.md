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



### What changed

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



### What changed

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

```
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
