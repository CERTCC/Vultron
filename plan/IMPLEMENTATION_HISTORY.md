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
