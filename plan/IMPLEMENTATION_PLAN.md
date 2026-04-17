# Vultron API v2 Implementation Plan

**Last Updated**: 2026-04-17 (INLINE-OBJ-C ✅ completed; 37 activity classes
now require `object_` at construction time; 1607 passed, 12 skipped, 182
deselected)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Full details for completed phases are in `plan/IMPLEMENTATION_HISTORY.md`.

**Priority ordering note:** `plan/PRIORITIES.md` is authoritative for project
priority. Section order here groups related work by execution context and MUST
NOT override `plan/PRIORITIES.md` when the two differ.

### Current Status Summary

**Test suite**: Canonical validation last passed on 2026-04-17
(1607 passed, 12 skipped, 182 deselected, 5581 subtests; `black`, `flake8`,
`mypy`, `pyright`, full `pytest` run).

All 38 message handlers implemented (including `unknown`). All 10 trigger
endpoints complete (including new `sync-log-entry`). 12 demo scripts, all
dockerized in `docker-compose.yml`.
All PRIORITY-30 through PRIORITY-200 phases complete.

#### Active open work

**PRIORITY-250** Pre-300 cleanup

- done: NAMING-1, QUALITY-1, SM-GUARD-1, VSR-ERR-1,
  BUG-FLAKY-1, REORG-1, SECOPS-1, DOCMAINT-1, SPEC-AUDIT-1, SPEC-AUDIT-2,
  SPEC-AUDIT-3

**PRIORITY-300** (multi-actor demos; D5-1 through D5-5 complete; D5-6 feedback
tasks tracked under PRIORITY-310 below).

**PRIORITY-310** Address demo feedback — D5-6-LOG, D5-6-STATE, D5-6-STORE,
D5-6-WORKFLOW (all ✅); D5-6-DUP, D5-6-TRIGDELIV, D5-6-LOGCTX (all ✅);
D5-6-DEMOAUDIT ✅; D5-6-AUTOENG ✅; D5-6-NOTECAST ✅; D5-6-CASEPROP ✅;
D5-6-EMBARGORCP ✅
**PRIORITY-320** Round-2 demo feedback (independent tasks) — all complete:
D5-7-EMSTATE-1 ✅, D5-7-AUTOENG-2 (superseded by D5-7-BTFIX-1),
D5-7-TRIGNOTIFY-1 ✅, D5-7-DEMONOTECLEAN-1 ✅, D5-7-MSGORDER-1 ✅,
D5-7-LOGCLEAN-1 ✅.
D5-7-CASEREPL-1 and D5-7-ADDOBJ-1 superseded by SYNC-2 (see Priority 330).
D5-7-BTFIX-1 ✅ and D5-7-BTFIX-2 ✅ (BT cascade violations); see IDEA-26041004.

**PRIORITY-325** ~~TinyDB → SQLModel/SQLite datalayer migration — DL-SQLITE-ADR,
DL-SQLITE-1, DL-SQLITE-2, DL-SQLITE-3, DL-SQLITE-4, DL-SQLITE-5 (all pending).
Addresses IDEA-26040902; supersedes IDEA-26040901.~~ **COMPLETE**.
Must complete before D5-7-HUMAN.

**PRIORITY-330** SYNC + demo sign-off — OUTBOX-MON-1 ✅, SYNC-1 ✅, SYNC-2 ✅,
SYNC-3 ✅; SYNC-TRIG-1 ✅ (new `sync-log-entry` trigger endpoint);
D5-7-DEMOREPLCHECK-1 ✅ (finder replica verification in two-actor demo);
INLINE-OBJ-A ✅, INLINE-OBJ-B ✅, INLINE-OBJ-C ✅ (inline object enforcement).
BUG-26041602 ✅ (CaseActor auto-sync emission).
D5-7-HUMAN blocked pending P-347 completion (see below).
SYNC-2 subsumes D5-7-CASEREPL-1 and D5-7-ADDOBJ-1.
Prereq for SYNC-2: D5-7-TRIGNOTIFY-1 (from Priority 320).

**PRIORITY-340** Wire-domain translation boundary — WIRE-TRANS-01–05 ✅.
Renames wire `VultronObject` → `VultronAS2Object`, adds `from_core()`/`to_core()`
stubs, implements on all wire object and activity types, deletes `serializer.py`.
See `specs/architecture.md` ARCH-12-001–007 and `notes/domain-model-separation.md`.

**PRIORITY-345** DataLayer auto-rehydration.

- [ ] **DL-REHYDRATE**: Implement auto-rehydration in the SQLite/TinyDB
  DataLayer adapters so that `dl.read()` and `dl.list()` always return fully
  typed domain objects with all dehydrated fields (`object_`, `target`,
  `origin`) restored to their original types. Once implemented, audit and
  remove all manual `model_validate` coercion scattered across
  `vultron/core/use_cases/` (currently in `triggers/embargo.py`,
  `triggers/report.py`, `received/sync.py`).
  See `specs/datalayer.md` DL-01-001 through DL-01-004 and
  `notes/datalayer-design.md`.

**PRIORITY-347** Demo puppeteering, trigger completeness, and BT node
generalization (see `plan/IMPLEMENTATION_NOTES.md` BUG-26041701 for full
context and design rationale). All tasks below are prerequisites for
**D5-7-HUMAN** sign-off.

- [ ] **P347-BUGFIX**: Fix `CreateFinderParticipantNode.update()` in
  `vultron/core/behaviors/case/nodes.py`: replace
  `VultronActivity(type_="Add", object_=participant.id_, ...)` with
  `AddParticipantToCaseActivity(object_=participant, ...)`.
  Refs: BUG-26041701, MV-09-001.

- [ ] **P347-NODEGENERAL**: Generalize `CreateFinderParticipantNode` →
  `CreateCaseParticipantNode(actor_id, role)` so that the node is
  parameterized and not hard-coded to the finder/reporter role.
  The existing call site(s) should pass role and actor identity as
  constructor arguments.
  Update all call sites and tests.
  Refs: IDEA-26041702.

- [ ] **P347-BRIDGE**: Extend the outbox expansion bridge in
  `vultron/core/use_cases/received/outbox_handler.py` from
  `("Create", "Announce")` to also include `"Add"`, `"Invite"`, and
  `"Accept"`. Document that `"Join"` and `"Remove"` will need the same
  treatment when implemented.

- [ ] **P347-SUGGESTBT**: Implement a proper BT in
  `SuggestActorToCaseReceivedUseCase.execute()`:
  - Precondition: the receiving actor is the case owner
    (`case.attributed_to == actor_id`); skip silently if not.
  - Emit `AcceptActorRecommendationActivity(to=[recommender_id])` and queue
    in outbox.
  - Emit `RmInviteToCaseActivity(actor=case_actor, object_=invitee,
    target=case, to=[invitee_id])` and queue in outbox.
  - Idempotent: if an invite for this actor+case already exists in the
    DataLayer, skip and log.
  Update tests to verify both activities are emitted and idempotency holds.

- [ ] **P347-TRIGGERS**: Add new trigger endpoints:
  - `create-case` and `add-report-to-case` in
    `vultron/adapters/driving/fastapi/routers/trigger_case.py` with
    corresponding `SvcCreateCaseUseCase` and `SvcAddReportToCaseUseCase` in
    `vultron/core/use_cases/triggers/`.
  - New router file `trigger_actor.py` with `suggest-actor-to-case` and
    `accept-case-invite` trigger endpoints, backed by
    `SvcSuggestActorToCaseUseCase` and `SvcAcceptCaseInviteUseCase`.

- [ ] **P347-EMBARGOTRIGGERS**:
  - Rename `evaluate-embargo` endpoint → `accept-embargo` (update router,
    `_trigger_adapter.py`, `SvcEvaluateEmbargoUseCase` → `SvcAcceptEmbargoUseCase`,
    all call sites, tests, and spec references).
  - Add `reject-embargo` trigger endpoint + `SvcRejectEmbargoUseCase`.
  - Add `propose-embargo-revision` trigger endpoint +
    `SvcProposeEmbargoRevisionUseCase`.
  - Update `specs/triggerable-behaviors.md` to reflect all embargo trigger
    renames and additions.

- [ ] **P347-DEMOORG**: Reorganize `vultron/demo/` into two sub-packages:
  - `vultron/demo/exchange/` — individual protocol-fragment demos
    (direct inbox injection; demonstrating message semantics).
    Move: all single-activity demos (`receive_report_demo.py`,
    `suggest_actor_demo.py`, `establish_embargo_demo.py`, etc.).
  - `vultron/demo/scenario/` — end-to-end multi-actor workflow demos
    (trigger-based puppeteering).
    Move: `two_actor_demo.py`, `three_actor_demo.py`,
    `multi_vendor_demo.py`.
  - Update `vultron/demo/cli.py`, all Docker Compose files, and Makefile
    imports/references.
  - Add `README.md` to each sub-package explaining the distinction.

- [ ] **P347-PUPPETEER**: Convert scenario demos to trigger-based
  puppeteering:
  - `three_actor_demo.py`: replace `coordinator_creates_case_on_case_actor`,
    `coordinator_adds_report_to_case`, `coordinator_invites_actor`,
    `actor_accepts_case_invite`, and `actor_accepts_embargo` with calls to
    the trigger endpoints added in P347-TRIGGERS and P347-EMBARGOTRIGGERS.
  - `multi_vendor_demo.py`: same pattern for its equivalent spoofing
    functions.
  - `two_actor_demo.py`: audit and convert any remaining direct inbox
    injections.

- [ ] **P347-SPECS**: Spec and notes updates:
  - `specs/triggerable-behaviors.md`: reflect trigger renames and additions
    from P347-EMBARGOTRIGGERS; add `create-case`, `add-report-to-case`,
    `suggest-actor-to-case`, `accept-case-invite`.
  - `specs/multi-actor-demo.md`: add requirement that scenario demos MUST
    use trigger endpoints (not direct inbox injection) for all actor-initiated
    actions.
  - `notes/protocol-event-cascades.md`: document the 4-step
    suggest→invite→accept→record cascade as a concrete named example.

**PRIORITY-360** BT composability audit (IDEA-26041703). Can proceed in
parallel with P-347.

- [ ] **P360-NOTES**: Create `notes/bt-reusability.md` capturing the fractal
  composability pattern from `vultron/bt/`, the "trunkless branch" intent,
  and anti-patterns (one-off nodes, hard-coded actor roles, demo-specific
  subtrees). Reference `notes/vultron-bt.txt` as the canonical BT structure
  blueprint.

- [ ] **P360-SPEC**: Create `specs/behavior-tree-node-design.md` with formal
  requirements for BT node parameterization and composability, e.g.:
  - BT nodes MUST NOT hard-code actor roles; identity and role MUST be
    constructor parameters.
  - Reusable logic that appears in multiple subtrees MUST be extracted into
    a shared composable subtree.
  - New BT subtrees SHOULD be verified against `notes/vultron-bt.txt` to
    confirm they match the intended structure.

- [ ] **P360-AUDIT**: Audit existing BT nodes in `vultron/core/behaviors/`
  against the above requirements. Produce a task list of nodes/subtrees
  requiring refactoring.

---

## Completed Phases

> Full implementation details are in `plan/IMPLEMENTATION_HISTORY.md`.
> Each tombstone references the HISTORY section(s) for context.

- **Phases 0/0.5** — Report demo, test infrastructure fix (2026-02-13)
- **BT-1 through BT-8** — BT integration POC, all protocol handlers (2026-02-18 to 2026-02-24)
- **DEMO-3/4, BUGFIX-1, REFACTOR-1** — Demo scripts, pytest logging noise,
  CM-03-006 status history renames (2026-02-24 to 2026-02-27)
- **TECHDEBT-1, 5, 6; SPEC-COMPLIANCE-1/2** — Early housekeeping, object model
  gaps, embargo policy model (2026-02-27 to 2026-03-06)
- **SPEC-COMPLIANCE-3 partial; PRIORITY-30 partial (P30-1–P30-3)** — Embargo
  acceptance tracking, first three trigger endpoints (2026-03-06)
- **P30-4, P30-6; ARCH-1.1–1.3** — close-report endpoint, demo CLI trigger
  sub-command, MessageSemantics moved to core, wire layer split into
  parser + extractor (2026-03-09)
- **PRIORITY-50/60/65 (P65-1–P65-7)** — Hexagonal architecture refactor,
  package relocation, VultronEvent typed hierarchy, wire imports removed from
  core (2026-03-10 to 2026-03-11)
- **SPEC-COMPLIANCE-3 complete; TECHDEBT-7–10, 13a/b/c; ARCH-DOCS-1** —
  Embargo tracking complete, NonEmptyString rollout, pyright baseline,
  BT pre-case events, wire-boundary cleanup, architecture-review.md updated
  (2026-03-10 to 2026-03-11)
- **PRIORITY-70 (P70-2–P70-5)** — DataLayer refactor into ports and adapters
  (2026-03-11)
- **PRIORITY-75 (P75-1–P75-5) + TECHDEBT-14** — Business logic →
  `core/use_cases/`, UseCase interface, CLI + MCP adapters, `api/v1` removed,
  `vultron_types.py` split (2026-03-12 to 2026-03-17)
- **TECHDEBT-15, 16** — Flaky test fix, DRY `VultronObject` base class
  (2026-03-16 to 2026-03-18)
- **PRIORITY-80 Batches 80a–80e (TECHDEBT-17–28)** — Dead code removal,
  wire-layer cleanup, `Received` suffix, `UseCase[Req,Res]` Protocol, error
  handling standardization (2026-03-16 to 2026-03-17)
- **DOCS-1, DOCS-2** — Docker README, broken inline code examples in `docs/`
  (2026-03-18 to 2026-03-19)
- **VCR Batch A (VCR-001, 006, 015a/b, 024, 028, 030–032)** — Dead code and
  shim removal (2026-03-18)
- **PREPX-1, PREPX-2, PREPX-3** — BT status string comparisons, handlers shim
  removal, `DispatchEvent`/`InboundPayload` deprecated aliases removed
  (2026-03-18)
- **VCR Batch B (VCR-003, 004, 007–009, 016–018)** — FastAPI adapter relocated
  to `vultron/adapters/driving/fastapi/` (2026-03-18)
- **VCR Batch C (VCR-019a/b/c/e, 020–023, 025–027, 029)** — `case_states/` →
  `core/`, RM/EM enums → `core/states/`, VultronEvent activity field cleanup
  (2026-03-18 to 2026-03-19)
- **VCR Batch D (VCR-010, 011, 012)** — Trigger service cleanup: `_trigger`
  suffix, abstract error-handling, URI validation deduplication (2026-03-19)
- **VCR-005** — Actor profile discovery endpoint (2026-03-19)
- **PRIORITY-85** — IDEAS.md extraction; all items captured in specs, notes,
  and plan (2026-03-19)
- **PRIORITY-90 (P90-1–P90-5)** — ADR-0013, RM state persisted via DataLayer,
  global STATUS dict removed, EM transition guards, health readiness probe,
  operation IDs (2026-03-23)
- **TECHDEBT-29–34, 36, 38** — Profile endpoint strings, split
  `test_handlers.py`, DataLayer boundary audit, EM transition guards, test
  helper centralization, `outbox_handler` crash fix (2026-03-23 to 2026-03-24)
- **OX-1.0–1.4** — `ActivityEmitter` port stub, delivery queue, outbox
  delivery loop (2026-03-19 to 2026-03-25)
- **TECHDEBT-30, 35, 37, 39** — Domain-specific event property getters,
  VultronEvent rich-object fix, `test/api/` removal, participant RM state
  consolidation (2026-03-23 to 2026-03-25)
- **PRIORITY-100 (ACT-1–3)** — ADR-0012, per-actor DataLayer isolation,
  trigger endpoints scoped to actor DataLayer (2026-03-23 to 2026-03-25)
- **VCR-014** — `actor_io.py` deleted; DataLayer inbox/outbox now canonical
  (2026-03-25)
- **PRIORITY-200 (CA-1–3)** — CaseActor broadcast on case update, action rules
  endpoint (2026-03-25 to 2026-03-26)
- **QUALITY-1** — `filterwarnings = ["error"]`, `TinyDbDataLayer.close()`
  (2026-03-26)
- **BUG-2026032601–603** — PytestCollectionWarning cleanup, `uv run` build fix
  (`git_describe_command`), test ordering dependency in DataLayer isolation
  tests (2026-03-26)

---

## Open Tasks

### Phase PRIORITY-250 — Pre-300 Cleanup (PRIORITY 250)

**Reference**: `plan/PRIORITIES.md` PRIORITY 250

Per `plan/PRIORITIES.md`, these tasks MUST be completed before D5-2 and later
PRIORITY-300 demo work. D5-1 (architecture review) MAY proceed in parallel.

#### NAMING-1 — Standardize wire-layer field naming ✅

- [x] **NAMING-1**: Renamed all `as_`-prefixed field names to trailing-underscore
  convention: `as_id` → `id_`, `as_type` → `type_`, `as_object` → `object_`,
  `as_context` → `context_`. All 130 affected files updated. Class names
  (`as_Activity`, `as_Object`, etc.) retain the `as_` prefix. Updated
  `specs/code-style.md` CS-07-001–003 and `AGENTS.md`. Completed 2026-03-30.

#### SECOPS-1 — CI security: ADR + automated pin-verification test ✅

- [x] **SECOPS-1**: Wrote `docs/adr/0014-sha-pin-github-actions.md`
  documenting the SHA-pinning + Dependabot policy. Implemented
  `test/ci/test_workflow_sha_pinning.py` (53 parametrised tests covering all
  `uses:` lines across 6 workflow files) verifying CI-SEC-01-001
  (40-char SHA) and CI-SEC-01-002 (version comment). Added ADR-0014 to
  `docs/adr/index.md`.

#### DOCMAINT-1 — Review and update outdated `notes/` files ✅

- [x] **DOCMAINT-1**: Updated `notes/activitystreams-semantics.md` (CaseActor
  broadcast now implemented), `notes/state-machine-findings.md` (Section 9
  fictional commits removed, OPP-05 and STATUS dict marked done),
  `notes/datalayer-refactor.md` (TECHDEBT-32b marked complete), and
  `notes/codebase-structure.md` (all old `vultron/api/v2/` path references
  updated to canonical current locations; outdated "not yet implemented"
  sections replaced with completion summaries). Completed 2026-03-30.

#### REORG-1 — Reorganize `vultron/core/use_cases/` ✅

- [x] **REORG-1**: Created `received/` sub-package for all 8 inbound
  message handler use cases and `query/` sub-package for `action_rules.py`.
  `_helpers.py` retained at root (shared by `received/` and `triggers/`).
  Tests mirrored to `test/core/use_cases/received/` and `query/`. README.md
  added documenting the trigger→received→sync information flow.

#### SM-GUARD-1 — Add named state-subset constants ✅

- [x] **SM-GUARD-1**: Exported `EM_NEGOTIATING` from `vultron/core/states/__init__.py`
  and replaced the inline `[EM.PROPOSED, EM.REVISE]` list in
  `vultron/bt/embargo_management/transitions.py` with `list(EM_NEGOTIATING)`.
  `RM_ACTIVE` and `RM_CLOSABLE` were already exported and integrated.

#### VSR-ERR-1 — Rename VultronConflictError to VultronInvalidStateTransitionError ✅

- [x] **VSR-ERR-1**: Renamed `VultronConflictError` to
  `VultronInvalidStateTransitionError` in `vultron/errors.py`; retained
  `VultronConflictError` as a deprecated alias. Updated all 5 raise sites in
  `triggers/embargo.py` and `triggers/report.py` to use the new name and added
  WARNING-level logging before each raise. Updated `fastapi/errors.py`
  isinstance check and all tests.

#### BUG-FLAKY-1 — Fix flaky test_remove_embargo ✅

- [x] **BUG-FLAKY-1**: Fixed `test_remove_embargo` in
  `test/wire/as2/vocab/test_vocab_examples.py` by extracting the embargo from
  the returned activity rather than recreating it with a new `datetime.now()`
  call.

---

### Phase PRIORITY-300 — Multi-Actor Demos (PRIORITY 300)

**Reference**: `plan/PRIORITIES.md` PRIORITY 300, `notes/demo-future-ideas.md`

**Note**: D5-1 is complete. D5-1-G1 through D5-1-G6 are the prerequisites
for D5-2, identified during the D5-1 architecture review. D5-2 and later
are blocked by all G tasks.

- [x] **D5-1**: Architectural review complete; CA-2 follow-up confirmed;
  `notes/multi-actor-architecture.md` produced with actor/container
  assumptions and D5-2 prerequisites (G1–G6). Completed 2026-03-31.

#### D5-1-G2 — Actor Seeding / Bootstrap CLI Command ✅

- [x] **D5-1-G2**: `vultron-demo seed` CLI sub-command implemented in
  `vultron/demo/cli.py`. Reads local actor + peer config from env vars
  (`VULTRON_ACTOR_NAME`, `VULTRON_ACTOR_TYPE`, `VULTRON_ACTOR_ID`) or a JSON
  file (`VULTRON_SEED_CONFIG`). Calls idempotent `POST /actors/` endpoint
  (added to `vultron/adapters/driving/fastapi/routers/actors.py`). Docker
  entrypoint (`docker/demo-entrypoint.sh`) calls `vultron-demo seed` when
  `VULTRON_ACTOR_NAME` or `VULTRON_SEED_CONFIG` is set. Full test coverage
  in `test/demo/test_seed_config.py`, `test/demo/test_seed.py`, and
  `test/adapters/driving/fastapi/routers/test_actors.py`.

#### D5-1-G4 — Multi-Container Docker Compose Configuration ✅

- [x] **D5-1-G4**: Created `docker/docker-compose-multi-actor.yml` with three
  actor services (`finder` port 7901, `vendor` port 7902, `case-actor` port
  7903) and a `demo-runner` service. Each actor service has a unique
  `VULTRON_BASE_URL`, named volume at `/app/data`, healthcheck at
  `/api/v2/health/ready`, and `vultron-network` membership. Added
  `VULTRON_DB_PATH` env var support to `get_datalayer()` via module-level
  `_DEFAULT_DB_PATH` constant (read from `os.environ` at import time). Added
  `RUN mkdir -p /app/data` to `docker/Dockerfile` api-dev target. Updated
  `docker/README.md` with multi-actor setup section. Added
  `test/adapters/driven/test_get_datalayer.py` (7 tests). Completed
  2026-03-31.

#### D5-1-G6 — Inbox URL Derivation Integration Test ✅

- [x] **D5-1-G6**: Added `test/adapters/driven/test_delivery_inbox_url.py`
  with 6 tests verifying that `DeliveryQueueAdapter`'s inbox URL derivation
  formula (`{actor_id}/inbox/`) produces URLs consistent with the FastAPI
  actors router route (`POST /actors/{actor_id}/inbox/`). Tests confirm the
  derivation normalises trailing slashes, preserves the actor UUID, and that
  a POST to the derived path returns 202 (not 404).

#### D5-1-G3 — CaseActor Instantiation Strategy ✅

- [x] **D5-1-G3**: Chosen strategy: pre-seeded container identity with
  lazy per-case `VultronCaseActor` records. For D5-2, CaseActor co-locates
  in Vendor container. Added deterministic `VULTRON_ACTOR_ID` values to
  `docker/docker-compose-multi-actor.yml`. Created
  `docker/seed-configs/seed-{finder,vendor,case-actor}.json` with full peer
  meshes. Updated `notes/multi-actor-architecture.md` §3-D and §4 gap
  list. Tests in `test/demo/test_multi_actor_seed.py` (32 tests).

#### D5-1-G5 — Multi-Container Demo Script ✅

- [x] **D5-1-G5**: Added `vultron/demo/two_actor_demo.py` plus a
  `vultron-demo two-actor` CLI sub-command for the Finder + Vendor
  multi-container workflow. The demo accepts per-container base URLs and
  deterministic actor IDs, seeds both containers in a two-phase peer-aware
  sequence, orchestrates cross-container inbox + trigger interactions for
  submit/validate/engage/invite/accept, and verifies final state from each
  container's DataLayer. Added unit coverage in
  `test/demo/test_two_actor_demo.py` and activated the `demo-runner` service
  in `docker/docker-compose-multi-actor.yml` with `DEMO=two-actor`.

#### D5-1-G1 — VULTRON_BASE_URL Exposure via Info/Health Endpoint ✅

- [x] **D5-1-G1**: Added `vultron/adapters/driving/fastapi/routers/info.py`
  with a `GET /info` endpoint returning `VULTRON_BASE_URL` and the list of
  actor IDs registered in the shared DataLayer. Registered in `v2_router.py`.
  Tests in `test/adapters/driving/fastapi/routers/test_info.py` (5 tests).
  The `/health/ready` DataLayer connectivity check (OB-05-002) was already
  implemented.

- [x] **D5-2**: Demo Scenario 1 (finder + vendor): Dockerized with two actor
  containers + CaseActor container. Completed 2026-03-31 with deterministic
  reset/seeding, stronger final-state assertions, and core validate-report
  seeding of the Vendor participant / actor-participant index.
- [x] **D5-3**: Demo Scenario 2 (finder + vendor + coordinator): added
  `vultron/demo/three_actor_demo.py` and `vultron-demo three-actor`, extended
  the multi-actor Docker setup with a `coordinator` service plus full seed
  mesh, and verified the authoritative case/embargo workflow on the dedicated
  `case-actor` container with unit coverage in
  `test/demo/test_three_actor_demo.py`. Completed 2026-04-01.
- [x] **D5-4**: Demo Scenario 3 (ownership transfer + multi-vendor). Implemented
  5-container demo (`multi_vendor_demo.py`) with Vendor-led case creation,
  ownership transfer to Coordinator, and Vendor2 invited into the active embargo
  group. Added seed-vendor2.json, updated all seed configs to 5-actor mesh,
  updated docker-compose-multi-actor.yml, added CLI command, and 6 unit tests.
  Also fixed `AcceptInviteToEmbargoOnCaseReceivedUseCase` idempotency bug that
  prevented per-participant embargo acceptance tracking. Completed 2026-04-01.
- [x] **D5-5**: Integration test script `run_multi_actor_integration_test.sh`
  created in `integration_tests/demo/`; accepts `two-actor`, `three-actor`, or
  `multi-vendor` as a positional argument (or via `DEMO` env var); builds
  images, runs the full multi-actor compose stack with
  `--abort-on-container-exit --exit-code-from demo-runner`, and removes
  volumes on exit. Added `make integration-test-multi-actor`,
  `integration-test-three-actor`, and `integration-test-multi-vendor` Makefile
  targets. Updated `integration_tests/README.md` and `docker/README.md` with
  usage notes. Completed 2026-04-01.
- [x] **D5-6**: Expanded into specific follow-up tasks D5-6-LOG, D5-6-STATE,
  D5-6-STORE, and D5-6-WORKFLOW in Phase PRIORITY-310 below, derived from
  reviewer feedback captured in `notes/two-actor-feedback.md`. See
  PRIORITY-310 section.

---

### Phase PRIORITY-310 — Address Demo Feedback (PRIORITY 310)

**Reference**: `plan/PRIORITIES.md` PRIORITY 310, `notes/two-actor-feedback.md`

Reviewer feedback on the two-actor multi-container demo is captured in
`notes/two-actor-feedback.md` (items D5-6a through D5-6l). All tasks in this
section MUST be completed before proceeding to other priorities.

#### D5-6-LOG — Improve process-flow logging across demo containers ✅

- [x] **D5-6-LOG**: Improved INFO-level logging for coherent process-flow
  across container logs (D5-6a, b, e, f, g). See IMPLEMENTATION_HISTORY.md.

#### D5-6-STATE — Clarify RM state log messages; initialize finder participant at RM.ACCEPTED ✅

- [x] **D5-6-STATE**: Fixed RM state transition log clarity and finder
  initial state initialization at RM.ACCEPTED (D5-6c). See
  IMPLEMENTATION_HISTORY.md.

#### D5-6-STORE — Verify and fix datalayer reference storage for nested activity objects ✅

- [x] **D5-6-STORE**: Datalayer stores nested objects by reference; logs
  clarified for rehydrated display (D5-6d). See IMPLEMENTATION_HISTORY.md.

#### D5-6-WORKFLOW — Automate complete case creation sequence from validate-report ✅

- [x] **D5-6-WORKFLOW**: Validate-report BT now executes full case creation
  (7-node sequence: case, embargo, vendor/finder participants, notification)
  as a single automated workflow (D5-6h). See IMPLEMENTATION_HISTORY.md.

#### D5-6-DUP — Investigate and fix duplicate VulnerabilityReport warning

- [x] **D5-6-DUP**: False-positive WARNING demoted to DEBUG in both
  `SubmitReportReceivedUseCase` and `CreateReportReceivedUseCase`; the inbox
  endpoint pre-stores nested objects before dispatch so duplicates are
  expected. Added `TestDuplicateReportHandling` tests confirming no WARNING
  on pre-stored report.

#### D5-6-LOGCTX — Improve outbox activity log messages with human-readable context ✅

- [x] **D5-6-LOGCTX**: Improved log messages for outbox activity queuing and
  delivery. Completed 2026-04-07.

#### D5-6-TRIGDELIV — Fix trigger endpoints to deliver outbox activities ✅

- [x] **D5-6-TRIGDELIV**: Added `BackgroundTasks` to all 9 trigger endpoints
  and scheduled `outbox_handler(actor_id, actor_dl, shared_dl)` as a background
  task after each use-case execution. Added 8 new tests verifying
  `outbox_handler` is scheduled. Completed 2026-04-07.

#### D5-6-DEMOAUDIT — Audit and refactor all demos for protocol compliance ✅

- [x] **D5-6-DEMOAUDIT**: Audited multi-actor demo scripts against protocol
  docs. Added `to=addressees` and full case embedding to
  `CreateCaseActivity` node (validate-report BT); added `to=[finder_actor_id]`
  to `CreateFinderParticipantNode` notification; fixed outbox_handler to expand
  `Create` activity objects before delivery; added `wait_for_finder_case()`
  polling helper + verification block to `run_two_actor_demo`. Documented
  remaining gaps as D5-6-AUTOENG, D5-6-NOTECAST, D5-6-EMBARGORCP,
  D5-6-CASEPROP. Completed 2026-04-07. See `plan/IMPLEMENTATION_HISTORY.md`.

#### D5-6-AUTOENG — Auto-engage after invitation acceptance

- [x] **D5-6-AUTOENG**: `AcceptInviteActorToCaseReceivedUseCase` now invokes
  `SvcEngageCaseUseCase` after participant creation, queues an
  `RmEngageCaseActivity`, and the three-actor / multi-vendor demos no longer
  call `engage-case` manually. Completed 2026-04-08.

#### D5-6-NOTECAST — Broadcast notes to case participants

- [x] **D5-6-NOTECAST**: When a note is added to a case, the CaseActor
  MUST broadcast the note to all case participants (excluding the note
  author).
  - Modified `AddNoteToCaseReceivedUseCase` to derive recipients from
    `case.actor_participant_index` and queue a broadcast `AddNoteToCaseActivity`
    to the outbox via `record_outbox_item`.
  - Removed manual note-forwarding code from the two-actor demo
    (`vultron/demo/two_actor_demo.py`).
  - Added three broadcast tests to `test/core/use_cases/received/test_note.py`.
  - **Spec**: CM-06-005, OX-03-001.
  - Completed 2026-04-10. See `plan/IMPLEMENTATION_HISTORY.md`.

#### D5-6-EMBARGORCP — Fix embargo Announce activity addressing

- [x] **D5-6-EMBARGORCP**: Removed the standalone `Announce(embargo)` from
  `InitializeDefaultEmbargoNode.update()`. Embargo info flows to the finder
  via `VulnerabilityCase.active_embargo` embedded in the `Create(Case)`
  activity. Tests updated; all linters and 1267 tests pass.
  Completed 2026-04-11. See `plan/IMPLEMENTATION_HISTORY.md`.

#### D5-6-CASEPROP — Case propagation and activity addressing

- [x] **D5-6-CASEPROP**: Fix remaining case propagation gaps (partially
  addressed in D5-6-DEMOAUDIT; D5-6-AUTOENG eliminated the manual
  `engage-case` demo step).
  - **Partial fix done** (D5-6-DEMOAUDIT): `CreateCaseActivity` node in
    `vultron/core/behaviors/report/nodes.py` (validate-report BT) now sets
    `to=addressees` and embeds the full `VulnerabilityCase` as `object_`.
    `CreateFinderParticipantNode` now sets `to=[finder_actor_id]`.
  - **Remaining gap closed** (D5-6-CASEPROP): `EmitCreateCaseActivity` in
    `vultron/core/behaviors/case/nodes.py` (create-case BT) now reads the
    full `VulnerabilityCase` via the DataLayer, embeds it as `object_`, and
    derives `to` from `actor_participant_index` (excluding the actor itself),
    matching the `report/nodes.py::CreateCaseActivity` pattern.
  - **Spec**: OX-03-001, DEMO-MA-00-001.
  - Completed 2026-04-10. See `plan/IMPLEMENTATION_HISTORY.md`.

#### BUG-26041602 — CaseActor auto-sync emission ✅

- [x] **BUG-26041602**: Fixed. Added `CommitCaseLogEntryNode` as a composable
  BT node (final child of `CreateCaseBT`, `EngageCaseBT`, `DeferCaseBT`,
  `ReceiveReportCaseBT`). `OutboxMonitor` delivers reactively; no inbound
  handler changes needed. Removed package-level re-exports from
  `triggers/__init__.py` to break the circular import chain.

#### D5-7-HUMAN — Project owner sign-off on demo feedback resolution

- [ ] **D5-7-HUMAN**: Project owner sign off. Agents are forbidden from updating
  this task; a human must confirm that all of the following are complete before
  signing off:
  - All D5-7 independent tasks (EMSTATE-1, AUTOENG-2, TRIGNOTIFY-1,
    DEMONOTECLEAN-1)
  - SYNC-2 (log replication; subsumes CASEREPL-1 and ADDOBJ-1)
  - D5-7-DEMOREPLCHECK-1 (post-SYNC-2 finder replica verification)
  - INLINE-OBJ-A ✅, INLINE-OBJ-B ✅, INLINE-OBJ-C ✅ (inline object
    enforcement; blocks recurring BUG-26041601 pattern; see IDEA-26041601)
  - BUG-26041602 (CaseActor auto-sync emission; must be fixed)
  - Multi-actor demos pass end-to-end with log-sync in place

---

### Phase PRIORITY-320 — Two-Actor Demo Feedback Round 2 (PRIORITY 320)

**Reference**: `notes/two-actor-feedback.md` Review Pass 2 (D5-7-* items),
`plan/PRIORITIES.md` PRIORITY 320

Second-pass review of the 2026-04-10 two-actor integration log identified
several concerns. The following tasks are **independent of SYNC** and should
be completed before starting SYNC work.

**Deferred to SYNC-2 scope** (Priority 330): D5-7-CASEREPL-1 and
D5-7-ADDOBJ-1 are superseded by the `Announce(CaseLogEntry)` replication path.

**Deferred until after SYNC-2**: D5-7-DEMOREPLCHECK-1 (log-state consistency
check) and D5-7-HUMAN (final sign-off).

See `notes/two-actor-feedback.md` for detailed observations and log line
references.

#### D5-7-CASEREPL-1 — Replace create-case handler with replication use case ~~SUPERSEDED~~

> **Superseded by SYNC-2.** The SYNC-2 log-replication design replaces the
> direct `Create(VulnerabilityCase)` vendor→finder delivery path with
> `Announce(CaseLogEntry)` replication via the CaseActor. Implementing a
> stopgap `ReceiveCreateCaseUseCase` here would be deleted/replaced by
> SYNC-2. The case identity and participant-ID correctness problems this
> task addressed are resolved by having the CaseActor be the sole writer of
> canonical log entries that participants replicate. See SYNC-2 for the
> authoritative fix; see `notes/case-log-authority.md` for rationale.
>
> **Fixes**: NEW-1, NEW-12 — addressed by SYNC-2.

#### D5-7-MSGORDER-1 — Create(Case) must precede Add(CaseParticipant) in outbox queue

- [x] **D5-7-MSGORDER-1**: The case-creation BT queues `Add(CaseParticipant)` for
  the finder participant (line 472) *before* `Create(Case)` (line 475). When the
  finder's outbox processes in order, the `Add` arrives before the case exists
  in the finder's datalayer, causing a "case not found" warning (line 516).

  **Fix**:
  - Reorder the BT nodes in `vultron/core/behaviors/case/nodes.py`
    (`EmitCreateCaseActivity`) so `Create(Case)` is queued before
    `Add(CaseParticipant)` notifications.
  - Verify with an integration test or log inspection that the finder no longer
    warns "case not found" on `Add(CaseParticipant)` receipt.

  **Spec**: `specs/outbox.md` OX-03-001 (delivery order); `notes/case-log-authority.md`.
  **Fixes**: NEW-3.

#### D5-7-EMSTATE-1 — Embargo initialization must update CaseStatus EM state

- [x] **D5-7-EMSTATE-1**: After embargo initialization, `caseStatuses[0].emState`
  remains `"NONE"` even though `activeEmbargo` is set to a valid embargo ID
  (visible in final state check, lines 831 and 839 of the 2026-04-10 log). The
  embargo is created and attached to the case but the CaseStatus is never updated
  to reflect it.

  **Fix**:
  - After `InitializeDefaultEmbargoNode` attaches the embargo, append a new
    `CaseStatus` entry with `em_state` reflecting the embargo's initial protocol
    state (e.g., `EM.PROPOSED` or as specified by `specs/case-management.md`).
  - Use `case.record_event(embargo.id_, "embargo_initialized")` per the trusted
    timestamp pattern.
  - Add tests verifying `caseStatuses[-1].emState != "NONE"` after case creation.

  **Spec**: `specs/case-management.md` CM-03-006, CM-03-007; AGENTS.md
  "case_status Field Is a List".
  **Fixes**: NEW-5.

#### D5-7-LOGCLEAN-1 — Replace verbose Pydantic repr in outbox delivery log

- [x] **D5-7-LOGCLEAN-1**: The outbox delivery INFO log at
  `vultron/adapters/driving/fastapi/outbox_handler.py` (line ~150) includes the
  full Pydantic `repr()` of the activity object (line 579 of the 2026-04-10 log),
  producing hundreds of characters of unreadable output.

  **Fix**:
  - Replace `activity_object` in the log format string with a concise helper
    that returns `f"{type(obj).__name__} {getattr(obj, 'id_', str(obj))}"` or
    similar — producing e.g. `VulnerabilityCase urn:uuid:8d52cb56-…`.
  - Ensure the helper handles string objects (already-serialized ID refs) and
    `None` gracefully.
  - Add a test verifying the delivery log message does not contain Pydantic
    field repr syntax (e.g. `context_=`, `type_=<`).

  **Fixes**: NEW-6.

#### D5-7-AUTOENG-2 — Auto-cascade from validate-report to engage-case or defer-case ~~SUPERSEDED~~

> **Implementation approach updated by IDEA-26041004.** The original fix
> description called for invoking `SvcEngageCaseUseCase` "inline" — a
> procedural call. This violates BT-06-005/BT-06-006. The correct
> implementation is D5-7-BTFIX-1 below.

- [x] **D5-7-AUTOENG-2**: After `validate-report` succeeds, the demo-runner
  manually triggers `engage-case`. The automated cascade is now tracked as
  **D5-7-BTFIX-1** with the correct BT-subtree implementation approach.

  **Superseded by**: D5-7-BTFIX-1.

#### D5-7-BTFIX-1 — Refactor validate→engage/defer cascade to BT subtree

- [x] **D5-7-BTFIX-1**: `SvcValidateReportUseCase` (triggers/report.py:170)
  and `ValidateCaseUseCase` (received/case.py:499) both call
  `SvcEngageCaseUseCase().execute()` procedurally after the validate BT
  completes (`_auto_engage()` pattern). This violates BT-06-005/BT-06-006:
  the validate→engage/defer cascade is invisible at the BT level.

  **Root cause**: The cascade was implemented as a procedural post-BT call
  rather than as a BT child subtree. The canonical CVD BT has
  `?_RMValidateBt → ?_RMPrioritizeBt` as a parent→child relationship;
  the prototype must mirror that structure.

  **Fix**:
  - Replace `_auto_engage()` in both `SvcValidateReportUseCase` and
    `ValidateCaseUseCase` with a `PrioritizeBt` child subtree inside the
    validate BT.
  - The `PrioritizeBt` subtree contains an `EvaluateCasePriorityNode`
    (fuzzer stub defaulting to SUCCESS → engage). On SUCCESS: engage subtree;
    on FAILURE: defer subtree.
  - The default priority-check node returns SUCCESS (engage immediately),
    preserving current demo behavior.
  - `execute()` calls only `bridge.execute_with_setup()` — no post-BT logic.
  - Remove the manual `engage-case` trigger from `two_actor_demo.py` after
    the cascade is automated.
  - Add tests verifying that after `validate-report` BT runs, the vendor
    participant's RM state is `ACCEPTED` without any separate trigger call.

  **This is the SSVC evaluator connection point** per IDEA-26041004: the
  `EvaluateCasePriorityNode` fuzzer stub is exactly where an SSVC decision
  engine will plug in.

  **Spec**: `specs/behavior-tree-integration.md` BT-06-005, BT-06-006;
  `notes/canonical-bt-reference.md` (prioritize subtree detail);
  `notes/protocol-event-cascades.md`.
  **Fixes**: D5-7-AUTOENG-2, IDEA-26041004.

#### D5-7-BTFIX-2 — Refactor AcceptInviteActorToCase to use BT

- [x] **D5-7-BTFIX-2**: `AcceptInviteActorToCaseReceivedUseCase`
  (received/actor.py:243) calls `SvcEngageCaseUseCase().execute()` procedurally
  with NO BT at all. The invitation-acceptance → engagement cascade should be
  expressed as a BT subtree.

  **Root cause**: D5-6-AUTOENG was implemented with a procedural shortcut
  rather than as a proper BT subtree. The canonical BT shows
  invitation-acceptance as a branch of `ReceiveMessagesBt` that leads to
  `RMPrioritizeBt`.

  **Fix**:
  - Implement `AcceptInviteActorToCaseBt` with the engagement cascade as a
    child subtree (same `PrioritizeBt` from D5-7-BTFIX-1 or a shared instance).
  - Replace the procedural `SvcEngageCaseUseCase().execute()` call with the
    BT execution pattern.
  - `execute()` contains only infrastructure glue.
  - Add tests verifying invite-acceptance triggers RM→ACCEPTED via BT, not
    procedurally.

  **Spec**: `specs/behavior-tree-integration.md` BT-06-001, BT-06-005, BT-06-006;
  `notes/canonical-bt-reference.md`.
  **Fixes**: IDEA-26041004 (partial).

#### D5-7-ADDOBJ-1 — Always inline `object` field in outbound Add/Create activities ~~SUPERSEDED~~

> **Superseded by SYNC-2.** The root cause (finder receiving `Add(CaseParticipant)`
> with a URI-only `object` field from the vendor) is eliminated when SYNC-2
> routes all case state updates through the CaseActor's `Announce(CaseLogEntry)`
> replication path — participant actors no longer receive direct `Add/Create`
> activities from peers. The inline-objects principle remains valid and will be
> applied to `Announce(CaseLogEntry)` delivery in SYNC-2's implementation.
>
> **Fixes**: NEW-8, NEW-9 — addressed by SYNC-2.

#### D5-7-TRIGNOTIFY-1 — Populate `to` field in all trigger-use-case outbound activities

> **Prerequisite for SYNC-2.** Trigger activities need correct `to` addressing
> to reach the CaseActor and be included in replication fan-out. Complete
> this task (in Priority 320) before starting SYNC-2.

- [x] **D5-7-TRIGNOTIFY-1**: Trigger use cases that emit outbound state-change
  activities (engage-case, defer-case, close-case, etc.) construct activities with
  no `to` field. The outbox handler silently drops them at DEBUG level ("No
  recipients found"), so case participants never receive these state notifications.
  For example, after `SvcEngageCaseUseCase` executes (line 640–641), the queued
  `RmEngageCaseActivity` (`urn:uuid:06492e44-…`, line 644) is silently dropped —
  the finder never learns the vendor engaged the case.

  **Fix**:
  - In each trigger use case that creates an outbound activity, populate the
    activity's `to` field with all current case participants from
    `case.actor_participant_index`, excluding the triggering actor.
  - At minimum audit: `SvcEngageCaseUseCase`, `SvcDeferCaseUseCase`,
    `SvcCloseCaseUseCase`, `SvcCloseReportUseCase`, and all embargo trigger
    use cases.
  - Add tests verifying each trigger use case queues activities with non-empty
    `to` fields matching the expected participant list.

  **Spec**: `specs/outbox.md` OX-03-001; `specs/case-management.md` CM-06.
  **Fixes**: NEW-13.

#### D5-7-DEMONOTECLEAN-1 — Use trigger API for notes in two-actor demo

- [x] **D5-7-DEMONOTECLEAN-1**: The two-actor demo directly POSTs
  `Create(Note)` and `Add(Note)` activities to the vendor's inbox on behalf of
  the finder (lines 648–695), bypassing the trigger API and the finder's outbox.
  This is a demo shortcut that does not reflect real deployment behavior.

  **Fix**:
  - Replace the direct inbox POST with a call to the finder's trigger endpoint:
    `POST /actors/{finder_id}/trigger/add-note-to-case`.
  - The note will flow: finder trigger → finder outbox → vendor inbox → vendor
    `AddNoteToCaseReceivedUseCase` → fan-out (D5-6-NOTECAST).
  - Verify in the demo log that the finder triggers the note, the finder's
    outbox delivers it to the vendor, and the vendor logs receipt.

  **Fixes**: NEW-4.

#### D5-7-DEMOREPLCHECK-1 — Add finder replica verification to two-actor demo final state check

> **Depends on SYNC-2.** Meaningful finder-replica verification requires
> checking log-state consistency (same canonical log hash, matching
> `CaseLogEntry` history), not just field equality. Implement after SYNC-2
> is complete.

- [x] **D5-7-DEMOREPLCHECK-1**: The final state check (lines 805–853 of the
  2026-04-10 log) inspects only the vendor's datalayer. The finder's replica is
  never verified. This means replication failures pass all demo checks silently.

  **Fix** (post SYNC-2):
  - Add a finder replica verification block in `two_actor_demo.py` after the
    existing vendor state check.
  - Verify at minimum:
    - The same case ID exists in finder's datalayer
    - `actor_participant_index` in finder's copy matches vendor's (same UUIDs)
    - The same `activeEmbargo` ID is present
    - Log-state hash consistency (same last-replicated hash from CaseActor)
  - The participant-ID correctness check will pass once SYNC-2 delivers
    case state via `Announce(CaseLogEntry)` rather than `Create(VulnerabilityCase)`.

  **Fixes**: NEW-11 (and implicitly NEW-1/NEW-12 via SYNC-2).

---

### Phase PRIORITY-325 — TinyDB → SQLModel/SQLite Datalayer Migration (PRIORITY 325)

**Reference**: `plan/PRIORITIES.md` PRIORITY 325; IDEA-26040902 (primary);
IDEA-26040901 (superseded by this work).

**Motivation**: TinyDB rewrites the entire JSON file on every read/write
operation. As test coverage grew, this caused the suite to balloon from ~13 s
to 15+ minutes, requiring a `pytest_configure` monkey-patch to force
`MemoryStorage` globally — accidental complexity paid entirely to work around
a TinyDB limitation. The `DataLayer` port makes a backend swap tractable.

**Approach**: Single-table polymorphic SQLModel storage model in the adapter
layer. Domain models (Pydantic) are unchanged. SQLModel is imported only in
the adapter. Test isolation via `sqlite:///:memory:` eliminates all patching.

**Sequential dependency chain**: DL-SQLITE-ADR → DL-SQLITE-1 → DL-SQLITE-2
→ DL-SQLITE-3 → DL-SQLITE-4; DL-SQLITE-5 may run in parallel with 2–4.
All tasks must complete before D5-7-HUMAN (Priority 330).

> **IDEA-26040901 disposition**: The per-type table consolidation question
> (consolidate TinyDB tables into one) is **superseded** by this migration.
> The single-table polymorphic SQLModel adapter resolves it automatically.

#### DL-SQLITE-ADR — Write ADR for TinyDB → SQLModel/SQLite migration

- [x] **DL-SQLITE-ADR**: Write `docs/adr/0016-sqlmodel-sqlite-datalayer.md`
  - Motivation: O(n) I/O cost, test monkey-patch complexity (BUG-2026041001
    evidence), and why these are structural rather than fixable.
  - Decision: Single-table polymorphic SQLModel adapter in the adapter layer.
  - `VultronObjectRecord(id_, type_, actor_id, data: JSON)` schema.
  - Test isolation strategy: `sqlite:///:memory:` replaces TinyDB MemoryStorage
    monkey-patch.
  - Hex-arch compliance: SQLModel isolated to adapter layer; core unchanged.
  - Consequences: TinyDB removed; `VULTRON_DB_PATH` renamed `VULTRON_DB_URL`.

  **Addresses**: IDEA-26040902. **Supersedes**: IDEA-26040901 (table layout).

#### DL-SQLITE-1 — Implement `datalayer_sqlite.py`

- [x] **DL-SQLITE-1**: Create `vultron/adapters/driven/datalayer_sqlite.py`.
  - Define `VultronObjectRecord(SQLModel, table=True)` with columns:
    - `id_: str` — primary key
    - `type_: str` — indexed (replaces per-type table routing)
    - `actor_id: str | None` — indexed (actor-scoped queries)
    - `data: dict` — `Field(sa_column=Column(JSON))` — full Pydantic
      `model_dump(by_alias=True)` serialization
  - Define `InboxEntry(SQLModel, table=True)` and
    `OutboxEntry(SQLModel, table=True)` for queue operations (actor-scoped).
  - Implement `SqliteDataLayer(DataLayer)` class:
    - Constructor accepts a SQLAlchemy connection URL string.
    - Manages a SQLModel `Session` and creates tables on init.
    - Implements all `DataLayer` Protocol methods: `create`, `read`, `get`,
      `update`, `save`, `delete`, `all`, `by_type`, `get_all`, `count_all`,
      `clear_table`, `clear_all`, `ping`, `inbox_*`, `outbox_*`,
      `record_outbox_item`, `find_actor_by_short_id`, `find_case_by_report_id`.
    - Actor scoping: filter by `actor_id` column (mirrors TinyDB table-prefix
      logic).
    - Supports `sqlite:///path.sqlite` and `sqlite:///:memory:`.
  - Add unit tests in `test/adapters/driven/test_datalayer_sqlite.py` covering
    CRUD, actor scoping, inbox/outbox, and ping.

  **Depends on**: DL-SQLITE-ADR.

#### DL-SQLITE-2 — Update `get_datalayer()` factory and env var

- [x] **DL-SQLITE-2**: Wire the new adapter into the factory.
  - Move or rewrite `get_datalayer()` in `datalayer_sqlite.py` (or a new
    `vultron/adapters/driven/factory.py`).
  - Rename env var: `VULTRON_DB_PATH` → `VULTRON_DB_URL`.
  - New default: `sqlite:///mydb.sqlite` (relative to CWD).
  - Update all references to `VULTRON_DB_PATH` in source, docs, and tests.
  - **Absorbs TECHDEBT-32c** (Priority 350): remove the
    `from vultron.adapters.driven.datalayer_tinydb import get_datalayer`
    fallback in `vultron/wire/as2/rehydration.py`; make `dl` a required
    parameter or inject via a core-level port. Mark TECHDEBT-32c ✅.

  **Depends on**: DL-SQLITE-1.

#### DL-SQLITE-3 — Update test infrastructure

- [x] **DL-SQLITE-3**: Remove TinyDB test patches; configure SQLite in-memory
  for tests.
  - Delete the `pytest_configure` hook in `conftest.py` that monkey-patches
    `TinyDbDataLayer.__init__` to use `MemoryStorage`.
  - Delete the layered `force_tinydb_memory` autouse fixture (and the
    integration-test opt-out fixture that restores the original init).
  - Configure `VULTRON_DB_URL=sqlite:///:memory:` in the top-level
    `conftest.py` session fixture (or via `pyproject.toml`
    `[tool.pytest.ini_options] env`).
  - If per-test DB isolation is needed (e.g., for integration tests), add a
    fixture that creates a fresh in-memory engine and drops/recreates tables
    after each test.
  - Verify the full test suite passes with no TinyDB references.

  **Depends on**: DL-SQLITE-2.

#### DL-SQLITE-4 — Remove TinyDB adapter and dependency

- [x] **DL-SQLITE-4**: Erase TinyDB from the codebase.
  - Delete `vultron/adapters/driven/datalayer_tinydb.py`.
  - Run `uv remove tinydb` (updates `pyproject.toml` and `uv.lock`).
  - Search for any remaining `TinyDbDataLayer`, `datalayer_tinydb`, or
    `tinydb` references across source and tests; remove all of them.
  - Run `uv run black vultron/ test/ && uv run flake8 vultron/ test/ &&
    uv run mypy && uv run pyright` and the full test suite to confirm clean.

  **Depends on**: DL-SQLITE-3.

#### DL-SQLITE-5 — Update Docker configs and env files

- [x] **DL-SQLITE-5**: Update deployment configuration for the new env var.
  - Replace `VULTRON_DB_PATH` with `VULTRON_DB_URL` in all `docker/`
    env files and `docker-compose*.yml`.
  - Default value inside containers:
    `sqlite:////app/data/mydb.sqlite` (absolute path; volume-mounted at
    `/app/data/`).
  - Update `docker/README.md` if it documents the database path env var.

  **May run in parallel with**: DL-SQLITE-2 through DL-SQLITE-4.

---

### Phase PRIORITY-340 — Wire-Domain Translation Boundary (PRIORITY 340)

**Reference**: `specs/architecture.md` ARCH-12-001 through ARCH-12-007,
`notes/domain-model-separation.md` "Agreed Design Decisions (2026-04-15)"

This phase resolves the remaining wire/core coupling by establishing the
formal `from_core()` / `to_core()` translation contract across all wire types.
It eliminates the two-classes-named-`VultronObject` confusion, deletes the
legacy `serializer.py`, and closes the ARCH-01-001 violations in core trigger
modules.

**Must complete before starting new protocol features**, as wire/core coupling
is accruing technical debt with each feature addition.

#### WIRE-TRANS-01 — Rename wire VultronObject → VultronAS2Object ✅

- [x] **WIRE-TRANS-01-1**: Renamed `VultronObject` → `VultronAS2Object` in
  `vultron/wire/as2/vocab/objects/base.py`; removed compatibility shim; no
  external callers of the wire alias existed.

#### WIRE-TRANS-02 — Add from_core/to_core stubs to VultronAS2Object ✅

- [x] **WIRE-TRANS-02**: Added `_field_map: ClassVar[dict[str, str]] = {}`,
  `from_core()` (default JSON round-trip + field rename via `_field_map`), and
  `to_core()` (raises `NotImplementedError`) to `VultronAS2Object`; 14 new
  tests in `test/wire/as2/vocab/test_vultron_as2_object.py`.

#### WIRE-TRANS-03 — Implement from_core on all wire object types ✅

- [x] **WIRE-TRANS-03**: Added concrete `from_core()` and feasible `to_core()`
  conversions for `VulnerabilityCase`, `VulnerabilityReport`, `CaseActor`,
  `CaseParticipant`, `CaseStatus`, `ParticipantStatus`, and `CaseLogEntry`.
  Added shared wire-base helpers for reference ID normalization and reverse
  field-map application, plus focused regression coverage in
  `test/wire/as2/vocab/test_wire_domain_translation.py`.

#### WIRE-TRANS-04 — Generic activity from_core on wire activity base

- [x] **WIRE-TRANS-04**: Created `VultronAS2Activity(as_TransitiveActivity)` in
  `vultron/wire/as2/vocab/activities/base.py` with `from_core()` JSON round-trip
  and `_field_map` support; 4 tests added to `test_wire_domain_translation.py`.

#### WIRE-TRANS-05 — Delete serializer.py

- [x] **WIRE-TRANS-05**: Deleted `vultron/wire/as2/serializer.py` (no callers).

---

### Phase PRIORITY-350 — Maintenance and Tooling (PRIORITY 350)

**Reference**: `plan/PRIORITIES.md` PRIORITY 350

#### TOOLS-1 — Evaluate Python 3.14 compatibility

- [ ] **TOOLS-1**: Evaluate Python 3.14 compatibility. Run the test suite on a
  Python 3.14 branch; if tests pass without issue, update `requires-python` in
  `pyproject.toml` to `>=3.14`, and update docker base images to use Python
  3.14.

#### TECHDEBT-32c — Remove adapter import from `wire/as2/rehydration.py` ~~ABSORBED~~

> **Absorbed by DL-SQLITE-2 (Priority 325).** The TinyDB fallback import will
> be removed as part of the datalayer migration. No standalone action needed here.

- [x] **TECHDEBT-32c** ~~(absorbed by DL-SQLITE-2)~~: `vultron/wire/as2/rehydration.py` imports
  `from vultron.adapters.driven.datalayer_tinydb import get_datalayer` as a
  fallback when no `dl` is passed. This violates CS-05-001 (wire layer must not
  import from adapters). All production callers already pass `dl` explicitly;
  the fallback serves only old test paths.

  **Fix**:
  - Remove the `get_datalayer` import and fallback from `rehydration.py`.
  - Make `dl` a required parameter, or inject a core-level `DataLayerFactory`
    port if a fallback is genuinely needed.
  - Update any test paths that relied on the fallback to pass `dl` explicitly.

  **References**: `notes/datalayer-refactor.md` TECHDEBT-32c (archived);
  `specs/code-style.md` CS-05-001.

#### DOCS-3 — Update `notes/user-stories-trace.md`

- [ ] **DOCS-3**: Update `notes/user-stories-trace.md` (the traceability
  matrix) to map every user story in `docs/topics/user_stories` to the exact
  implementing requirements in `specs/`. Add a mapping for each story and mark
  stories lacking requirement coverage. Add a new section in
  `plan/IMPLEMENTATION_NOTES.md` listing stories with insufficient coverage.

#### CONFIG-1 — YAML configuration files with Pydantic schema validation

- [ ] **CONFIG-1**: Replace or supplement JSON/env-var actor configuration
  with YAML config files loaded into validated Pydantic models (IDEA-260402-01).
  - Load YAML into a dict (`yaml.safe_load()`), validate via a Pydantic
    `ActorConfig` model with typed nested sections (actor identity, peer
    mesh, DataLayer backend settings).
  - Replace the current `VULTRON_SEED_CONFIG` JSON path with a YAML
    equivalent; keep env-var overrides for backwards compatibility.
  - Update `vultron/demo/cli.py` `seed` sub-command to accept YAML seed
    configs in addition to JSON.
  - Add unit tests for round-trip load/validate of example seed configs.
  - `pyyaml` is already an indirect dependency (via `docker-compose` test
    helper); add `pyyaml` and `types-pyyaml` to `pyproject.toml` if not
    already present.

#### DOCMAINT-2 — Fix stale references to archived notes

- [ ] **DOCMAINT-2**: Several files still reference notes that were moved to
  `archived_notes/` or merged into other notes files (commit `0922e1f1`).
  Search for and update all stale cross-references.

  **Files moved to `archived_notes/`** — update references to use the new path:
  - `notes/state-machine-findings.md` → `archived_notes/state-machine-findings.md`
    (referenced in `plan/PRIORITIES.md`, `plan/IMPLEMENTATION_PLAN.md`,
    `specs/behavior-tree-integration.md`)
  - `notes/multi-actor-architecture.md` → `archived_notes/multi-actor-architecture.md`
    (referenced in `plan/IMPLEMENTATION_PLAN.md`)
  - `notes/two-actor-feedback.md` → `archived_notes/two-actor-feedback.md`
    (referenced in `plan/IMPLEMENTATION_PLAN.md`)
  - `notes/datalayer-refactor.md` → `archived_notes/datalayer-refactor.md`
    (referenced in `plan/IMPLEMENTATION_PLAN.md`)
  - `notes/architecture-review.md` → `archived_notes/architecture-review.md`
    (referenced in `specs/architecture.md`)

  **Files merged** — update references to point to the merged destination:
  - `notes/canonical-bt-reference.md` → `notes/bt-integration.md`
    (referenced in `plan/IDEAS.md`, `plan/IMPLEMENTATION_PLAN.md`,
    `specs/behavior-tree-integration.md`)

  **Also**: Update `notes/datalayer-sqlite-design.md` status header from
  "Status: Planned" to "Status: Complete".

---

### Phase PRIORITY-330 — Replicated Log Synchronization + Demo Sign-off (PRIORITY 330)

**Reference**: `plan/PRIORITIES.md` PRIORITY 330,
`plan/IMPLEMENTATION_NOTES.md` (2026-03-26 SYNC design notes)

> **Note on task/priority coupling**: Going forward, tasks in this section
> use explicit `Depends on:` notation rather than priority-group section
> headers, so that `plan/PRIORITIES.md` can be updated without requiring
> corresponding edits here.

These tasks implement distributed append-only case event log replication using
AS2 Announce activities as the transport. The CaseActor (acting as de facto
lead) maintains authoritative case event history and replicates it to
Participant Actors via log synchronization.

This block was formerly PRIORITY-400. It is elevated because D5-7-HUMAN
sign-off depends on SYNC-2 completing the participant replication story.

**Sequential dependency chain**: OUTBOX-MON-1 → SYNC-1 → SYNC-2 → SYNC-3
→ D5-7-DEMOREPLCHECK-1 → D5-7-HUMAN.
SYNC-2 also requires D5-7-TRIGNOTIFY-1 (from Priority 320) to be complete.

> **Design note:** Case Ownership and replication leadership are distinct
> concepts. A future ownership transfer likely implies leadership change,
> but a leadership change alone does not imply an ownership transfer.
>
> `notes/sync-log-replication.md` has been created capturing the RAFT-inspired
> design notes and system invariants. The corresponding entries in
> `plan/IMPLEMENTATION_NOTES.md` have been struck through.

#### OUTBOX-MON-1 — OutboxMonitor background loop

> **Prerequisite for SYNC-1/SYNC-2.** Moved from Priority 350.

- [x] **OUTBOX-MON-1**: Added `OutboxMonitor` in
  `vultron/adapters/driving/fastapi/outbox_monitor.py`; started/stopped in
  FastAPI lifespan (`app.py`). Polls all actor outboxes every 1 s and
  delivers via `outbox_handler`. 19 unit tests added.

#### SYNC-1 — Local append-only case event log with indexing

> **Depends on**: OUTBOX-MON-1.

- [x] **SYNC-1**: Implemented `CaseLogEntry`, `CaseEventLog`, and
  `ReplicationState` in `vultron/core/models/case_log.py`; added
  `is_leader` leadership guard port to `BTBridge`
  (`vultron/core/behaviors/bridge.py`). 52 new tests in
  `test/core/models/test_case_log.py`. See `plan/IMPLEMENTATION_HISTORY.md`
  for full details.

#### SYNC-2 — One-way log replication to Participant Actors

> **Depends on**: SYNC-1, OUTBOX-MON-1, D5-7-TRIGNOTIFY-1.
>
> **Subsumes**:
>
> - **D5-7-CASEREPL-1** — `Announce(CaseLogEntry)` replication replaces the
>   direct `Create(VulnerabilityCase)` path; no separate `ReceiveCreateCaseUseCase`
>   stopgap should be implemented.
> - **D5-7-ADDOBJ-1** — The inline-objects principle (embed full object, not
>   URI stub) is incorporated into `Announce(CaseLogEntry)` delivery;
>   the direct vendor→finder `Add`/`Create` path is retired.

- [x] **SYNC-2**: One-way log replication from CaseActor to Participant Actors
  via AS2 `Announce(CaseLogEntry)` activities. Requirements:
  - Strict conflict handling: reject mismatched `prev_log_hash`; respond with
    last-accepted hash (SYNC-03-001); sender retries from entry following the
    reported last-accepted hash (SYNC-03-002)
  - Idempotent delivery: duplicate replication messages MUST NOT create
    duplicate log entries (SYNC-03-003)
  - Log state in context: participants SHOULD include last-accepted log hash
    in `context` field of outbound messages to CaseActor (SYNC-03-004)
  - **Commit discipline** (SYNC-09-001, SYNC-09-002): External Vultron
    messages (including participant replication fan-out) MUST only be emitted
    after the associated `CaseLogEntry` is committed. In single-node this
    means after the append is durably written.
  - Reconcile "replication leadership" with "Case Ownership" (SYNC-06-001):
    distinct concepts; ownership transfer implies leadership change, but not
    vice versa.

#### SYNC-3 — Full sync loop with retry/backoff

- [x] **SYNC-3**: Full sync loop with retry/backoff. Depends on SYNC-2.

#### SYNC-4 — Multi-peer synchronization

- [ ] **SYNC-4**: Multi-peer synchronization with per-peer replication state.
  Enables RAFT consensus for CaseActor process. Depends on SYNC-3.

---

### Phase INLINE-OBJ — Enforce Inline Objects in Cross-Actor Activities

**Reference**: `plan/IDEAS.md` IDEA-26041601; root-cause analysis of
BUG-26041601 and BUG-26041501.

**Context**: `ActivityPattern._match_field` conservatively returns `True` for
any bare string URI (line 70-71 of `extractor.py`). This means any activity
whose `object_` is a string ID matches every pattern that checks `object_`
type — causing wrong-handler dispatch (the bug pattern seen in BUG-26041601
and BUG-26041501). `ActivityStreamRef[T]` = `T | as_Link | str | None`
is the permissive inbound-parsing alias; outbound construction must not
use it for fields whose type drives semantic extraction.

Three sequential sub-tasks address this at increasing generality. All three
are **prerequisites for D5-7-HUMAN** since the bug pattern recurs across
demos.

#### INLINE-OBJ-A — Fix Offer/Invite/Create: require inline objects at model + outbox layer

- [x] **INLINE-OBJ-A**: Narrowed initiating outbound activity `object_` fields
  from permissive refs to inline typed objects, added MV-09 outbound-object
  integrity requirements plus outbox enforcement, fixed all callers/examples,
  and updated regression coverage. Completed 2026-04-16.

  Scope: Offer/Invite/Create/Announce activities (and other initiating
  activities) in `vultron/wire/as2/vocab/activities/`. `AcceptXxx` /
  `RejectXxx` responses are handled in INLINE-OBJ-B.

  Deliverables:
  - Audit all activity classes in `vultron/wire/as2/vocab/activities/`
    for `object_: XxxRef` fields and change to the concrete type where
    the object is sent to a remote actor who may not have it.
  - Add a spec requirement to `specs/message-validation.md` (new section
    "Outbound Activity Object Integrity") requiring that outbound activities
    destined for other Actors carry full inline objects (not string ID
    references) in `object_` when the semantic type depends on the object
    type.
  - Add outbox-port validation (raise `VultronError` subclass) for
    activities where `object_` is a bare string or `as_Link` at
    send time.
  - Regression tests in `test/test_semantic_activity_patterns.py` and
    `test/wire/as2/vocab/activities/` covering each fixed activity class.

#### INLINE-OBJ-B — Fix Accept/Reject: require type-stub (not bare string ID) ✅

- [x] **INLINE-OBJ-B**: Changed `object_` type on all 12 Accept/Reject/TentativeReject
  activity classes from `XxxRef` (= `Xxx | as_Link | str | None`) to the concrete
  typed activity class (`XxxActivity | None`). Updated 9 demo files, trigger use
  cases (with storage-layer dehydration-aware coercion), `specs/response-format.md`,
  `AGENTS.md`, and `vultron/demo/utils.py`. Added regression tests in
  `test/wire/as2/vocab/test_actvitities/test_inline_object_required.py`.

#### INLINE-OBJ-C — Prohibit object_=None where semantics require a typed object ✅

- [x] **INLINE-OBJ-C**: Removed `| None` and `default=None` from `object_`
  fields on all 37 activity classes whose `ActivityPattern` inspects
  `object_.type`. Updated `triggers/embargo.py` to resolve `EmbargoEvent`
  from the data layer when the stored field is a dehydrated string.
  Added `MV-09-003` to `specs/message-validation.md`. Added
  `TestNoneObjectRejected` with 74 tests (37 classes × 2 checks each).
  1607 passed, 12 skipped, 182 deselected, 5581 subtests.

---

## Documentation Quality Tasks

These tasks were identified during the March 27, 2026 spec review session and
are needed before resuming feature development.

### SPEC-AUDIT-1 — Consolidation audit: eliminate redundant requirements ✅

- [x] **SPEC-AUDIT-1**: Audited all `specs/` files; identified and eliminated
  redundant requirements across four overlapping pairs. Deprecated CS-01-002,
  CS-01-003, CS-01-006 (superseded by canonical IMPL-TS-07-* in tech-stack.md).
  Removed duplicate implementation notes and duplicate verification test
  assertions from handler-protocol.md (covered by dispatch-routing.md).
  Added bidirectional cross-references across 6 spec files (dispatch-routing,
  handler-protocol, semantic-extraction, code-style, tech-stack, architecture).
  All 453 Markdown files pass markdownlint.

### SPEC-AUDIT-2 — Strength keyword migration ✅

- [x] **SPEC-AUDIT-2**: Every requirement line in all 37 spec files now has an
  RFC 2119 keyword on its first line (greppable). Prefix-style keywords are
  parenthesised: `` `ID` (MUST) text ``; naturally-embedded keywords left as-is.
  All section-header keyword suffixes (e.g. `(MUST)`) removed. 176 keyword
  additions, 293 header cleanups, 171 format fixes. Completed 2026-03-30.

### SPEC-AUDIT-3 — Relocate transient implementation notes from specs ✅

- [x] **SPEC-AUDIT-3**: Fixed all stale spec references: updated `test/api/v2/`
  test paths to canonical `test/adapters/` and `test/core/` locations across
  9 spec files; replaced `SEMANTIC_HANDLER_MAP` with `USE_CASE_MAP` in
  handler-protocol.md and semantic-extraction.md; removed/updated
  `@verify_semantics` decorator references in behavior-tree-integration.md,
  architecture.md, and testability.md; updated stale implementation paths in
  code-style.md, semantic-extraction.md, error-handling.md, outbox.md,
  idempotency.md, and response-format.md. Updated TB-04-001 test mirror paths.
  All VSR items (VSR-03-001, 03-003, 03-004, 07-002, 07-003, 09-002,
  PD-003, DR-001) were already incorporated in earlier passes.

### VOCAB-REG-1 — Vocabulary registry auto-registration

> **Design complete** as of 2026-04-08. See `notes/vocabulary-registry.md`
> for full design rationale. Spec updated in `specs/vocabulary-model.md`
> VM-01-001 through VM-01-006. Implementation split into two tasks below.

#### VOCAB-REG-1.1 — Redesign vocabulary registry core mechanics

- [x] **VOCAB-REG-1.1**: Implement the new registry mechanics in the
  `vultron/wire/as2/vocab/base/` package. Scope: infrastructure only;
  existing decorators remain in place until VOCAB-REG-1.2.
  - Created `vultron/wire/as2/vocab/base/enums.py` with `VocabNamespace`
    enum (`AS`, `VULTRON`)
  - Rewrote `vultron/wire/as2/vocab/base/registry.py`:
    - Replaced `Vocabulary(BaseModel)` with plain
      `VOCABULARY: dict[str, type[BaseModel]]` module-level singleton
    - Updated `find_in_vocabulary(name: str)` to flat-dict lookup,
      raises `KeyError` on miss
    - Removed `activitystreams_object`, `activitystreams_activity`,
      `activitystreams_link` decorator definitions
  - Updated `vultron/wire/as2/vocab/base/base.py` (`as_Base`):
    - Added `_vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.AS`
    - Added `__init_subclass__` that inspects new class's `type_`
      annotation and registers concrete types in `VOCABULARY`
  - Updated `vultron/wire/as2/vocab/objects/base.py` (`VultronObject`):
    - Overrides `_vocab_ns = VocabNamespace.VULTRON`
  - Completed 2026-04-10.

#### VOCAB-REG-1.2 — Migrate vocabulary classes and update callers

- [x] **VOCAB-REG-1.2**: Remove all `@activitystreams_*` decorator usages,
  add startup-guarantee discovery, and update all `find_in_vocabulary()`
  callers. Depends on VOCAB-REG-1.1.
  - Removed `@activitystreams_object` / `@activitystreams_activity` /
    `@activitystreams_link` decorators from all 16 vocab class files
    (74 call sites across `vocab/objects/`, `vocab/activities/`,
    `vocab/base/objects/`, `vocab/base/links.py`)
  - Added `pkgutil.iter_modules` + `importlib.import_module` dynamic
    discovery to `vocab/objects/__init__.py`, `vocab/activities/__init__.py`,
    `vocab/base/objects/__init__.py`, and
    `vocab/base/objects/activities/__init__.py`
  - Registered `as_Actor` explicitly (`VOCABULARY["Actor"] = as_Actor`) since
    it has no concrete `type_` annotation but is stored as type `"Actor"`
  - Updated all `find_in_vocabulary()` caller files to handle `KeyError`
  - Added activity-type check in `parser.py` (`issubclass(cls, as_Activity)`)
  - Added unit tests in `test/wire/as2/vocab/base/test_registry.py`
  - Added completeness tests in `test/wire/as2/vocab/base/test_registry_completeness.py`
  - Added BUG-26040902 regression test in
    `test/core/behaviors/case/test_bug_26040902_regression.py`
  - Completed 2026-04-10.

#### OUTBOX-MON-1 → moved to Priority 330 (SYNC block)

> **Moved**: OUTBOX-MON-1 is now the first task in Priority 330 (SYNC block)
> as it is a hard prerequisite for SYNC-1/SYNC-2. See the P330 section above.

### EMBARGO-DUR-1 — Update EmbargoPolicy model to ISO 8601 duration format

- [x] **EMBARGO-DUR-1**: Replaced integer `_days` fields with `timedelta`
  fields serialized as ISO 8601 duration strings. `_parse_duration()` helper
  rejects calendar units (Y, M-month, W). `InitializeDefaultEmbargoNode` reads
  `preferred_duration` via isodate. 20 new tests added (DUR-04, DUR-05).
  Completed 2026-04-09.

### FINDER-PART-1 — Create CaseParticipant at report receipt ~~SUPERSEDED~~

> **Superseded by ADR-0015** (Create VulnerabilityCase at Report Receipt).
> The case is now created at report receipt, so participant records are
> created atomically as part of case creation. The retroactive re-linking
> mechanism described below is no longer needed. See
> `docs/adr/0015-create-case-at-report-receipt.md` and the IDEA-260408-01
> tasks below.

- ~~[ ] **FINDER-PART-1**: Implement the report-as-proto-case participant
  lifecycle: create a `CaseParticipant` record for the finder at report
  receipt (not deferred to case creation) and retroactively re-link it to
  the case when one is created.~~

---

## IDEA-260408-01 — Case Creation at RM.RECEIVED

Per ADR-0015, `VulnerabilityCase` creation moves from `ValidateReport` BT
(RM.VALID) to `SubmitReportReceivedUseCase` (RM.RECEIVED). The tasks below
implement this change. All tasks depend on the documentation work captured
in ADR-0015, `specs/case-management.md` CM-12, and `specs/duration.md`
DUR-07-002/DUR-07-004.

### IDEA-260408-01-1 — Add DataLayer report→case lookup

- [x] **IDEA-260408-01-1**: Added `find_case_by_report_id(report_id: str) ->
  PersistableModel | None` to `DataLayer` Protocol and `TinyDbDataLayer`.
  Five unit tests added to `test/adapters/driven/test_tinydb_backend.py`.
  Completed 2026-04-08.

### IDEA-260408-01-2 — New BT: `receive_report_case_tree` ✅

- [x] **IDEA-260408-01-2**: Created
  `vultron/core/behaviors/case/receive_report_case_tree.py` and
  `test/core/behaviors/case/test_receive_report_case_tree.py`.
  Added `CheckCaseExistsForReport` node and `initial_rm_state` parameter to
  `CreateInitialVendorParticipant`. Completed 2026-04-08.

### IDEA-260408-01-3 — Refactor `SubmitReportReceivedUseCase`

- [x] **IDEA-260408-01-3**: Refactor `SubmitReportReceivedUseCase` in
  `vultron/core/use_cases/received/report.py` to invoke
  `receive_report_case_tree` via `BTBridge` (same pattern as
  `ValidateReportReceivedUseCase`).
  - Remove standalone `VultronParticipantStatus` record creation from this
    use case; all RM history now lives in `VultronParticipant.
    participant_statuses`.
  - Update `test/core/use_cases/received/test_submit_report.py` to verify
    case creation, participant creation, and `Create(Case)` queued to outbox.
  - Depends on IDEA-260408-01-2.

### IDEA-260408-01-4 — Slim `validate_report` BT

- [x] **IDEA-260408-01-4**: Remove case/participant/activity nodes from
  `vultron/core/behaviors/report/validate_tree.py`:
  - Remove: `CreateCaseNode`, `InitializeDefaultEmbargoNode`,
    `CreateInitialVendorParticipant`, `CreateFinderParticipantNode`,
    `CreateCaseActivity`, `UpdateActorOutbox`
  - Add: `EnsureEmbargoExists` condition node (verifies embargo exists
    before completing validation, per DUR-07-004)
  - Update `test/core/behaviors/report/test_validate_tree.py` to verify
    the slimmed tree does NOT create a case or participants.
  - Depends on IDEA-260408-01-2.

### IDEA-260408-01-5 — Dereference pattern for report use cases

- [x] **IDEA-260408-01-5**: Update `InvalidateReportReceivedUseCase`,
  `CloseReportReceivedUseCase`, and `ValidateReportReceivedUseCase` to
  dereference `report_id → case_id` using the DataLayer method from
  IDEA-260408-01-1, then delegate to `InvalidateCaseUseCase` /
  `CloseCaseUseCase` / `ValidateCaseUseCase` respectively.
  - Ensures all report-centric protocol activities can locate and update
    the case created at receipt (CM-12-005).
  - Add/update tests verifying the dereference pattern works correctly.
  - Depends on IDEA-260408-01-1.

### IDEA-260408-01-6 — Remove standalone `VultronParticipantStatus` records

- [x] **IDEA-260408-01-6**: Audit and remove standalone
  `VultronParticipantStatus` record creation in `CreateReport` and
  `AckReport` use cases (if any), as all RM history now lives in
  `VultronParticipant.participant_statuses`.
  - Verify no code path relies on flat `ReportStatus` as the primary RM
    carrier post-case-creation.
  - Depends on IDEA-260408-01-3.

### IDEA-260408-01-7 — Update tests

- [x] **IDEA-260408-01-7**: Added `TestFullReportFlow` integration tests to
  `test/core/use_cases/received/test_report.py` verifying: case created at
  RM.RECEIVED (not re-created at RM.VALID), vendor transitions to RM.VALID,
  finder stays RM.ACCEPTED, and full flow produces correct final state.
  Confirmed `test_validate_tree.py` already reflects ADR-0015.

---

## Deferred (Per PRIORITIES.md)

- USE-CASE-01 **`CloseCaseUseCase` wire-type construction** — Replace direct
  construction of
  `VultronActivity(as_type="Leave")` with domain event emission through the
  `ActivityEmitter` port. Defer until outbound delivery integration beyond
  OX-1.0 is implemented.
- USE-CASE-02 **UseCase Protocol generic enforcement** — Decide on a
  consistent
  `UseCaseResult` Pydantic return envelope; enforce via mypy. Defer to after
  TECHDEBT-21/22.
- **EP-02/EP-03** — EmbargoPolicy API + compatibility evaluation (`PROD_ONLY`)
- **AR-04/AR-05/AR-06** — Job tracking, pagination, bulk ops (`PROD_ONLY`)
- AGENTIC-00 **Agentic AI integration** (Priority 1000) — out of scope until
  protocol
  foundation is stable
- FUZZ-00 **Fuzzer node re-implementation** (Priority 500) — see
  `notes/bt-fuzzer-nodes.md`
- IDEA-260402-02 **Per-participant case replica management** — Each Participant
  Actor maintains their own copy of the case object, synchronised from the
  CaseActor via `Announce(CaseLogEntry)` replication. SYNC-1 through SYNC-4
  implement the CaseActor side; the participant-side case replica handler
  (routing inbound `Announce` to the correct local case copy) is part of
  SYNC-2 scope. See `plan/IDEAS.md` IDEA-260402-02 and
  `notes/sync-log-replication.md` for the design.
