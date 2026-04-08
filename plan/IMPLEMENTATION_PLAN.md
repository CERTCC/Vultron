# Vultron API v2 Implementation Plan

**Last Updated**: 2026-04-08 (D5-6-AUTOENG complete; canonical validation 1262
passing; three-actor and multi-vendor demos no longer require manual
`engage-case` triggers after invite acceptance)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Full details for completed phases are in `plan/IMPLEMENTATION_HISTORY.md`.

**Priority ordering note:** `plan/PRIORITIES.md` is authoritative for project
priority. Section order here groups related work by execution context and MUST
NOT override `plan/PRIORITIES.md` when the two differ.

### Current Status Summary

**Test suite**: Canonical validation last passed on 2026-04-08
(1262 passed, 5581 subtests; `black`, `flake8`, `mypy`, `pyright`, full
`pytest` run).

All 38 message handlers implemented (including `unknown`). All 9 trigger
endpoints complete. 12 demo scripts, all dockerized in `docker-compose.yml`.
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
D5-6-DEMOAUDIT ✅; D5-6-AUTOENG ✅; D5-6-NOTECAST, D5-6-EMBARGORCP,
D5-6-CASEPROP pending; D5-7 pending human sign-off.

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
section MUST be completed before proceeding to PRIORITY-350 and beyond. D5-7
(project owner sign-off) is the final gate for this phase.

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

- [ ] **D5-6-NOTECAST**: When a note is added to a case, the CaseActor
  MUST broadcast the note to all case participants (excluding the note
  author).
  - Modify `AddNoteToCaseReceivedUseCase` to derive recipients from
    `case.actor_participant_index` and queue a broadcast activity to
    the outbox.
  - Remove manual note-forwarding code from the two-actor demo
    (`vultron/demo/two_actor_demo.py`).
  - **Spec**: CM-06-005, OX-03-001.

#### D5-6-EMBARGORCP — Fix embargo Announce activity addressing

- [ ] **D5-6-EMBARGORCP**: The `InitializeDefaultEmbargoNode` creates
  an `Announce(embargo)` with no `to` field and runs before participants
  exist in the BT ordering.
  - Recommended fix: Remove the standalone `Announce(embargo)` from the
    validate-report BT and rely on the `Create(Case)` activity to carry
    embargo information via `VulnerabilityCase.active_embargo`.
  - Verify that the finder receives embargo info via the case object in
    the `Create(Case)` notification.
  - **Spec**: OX-03-001.

#### D5-6-CASEPROP — Case propagation and activity addressing

- [ ] **D5-6-CASEPROP**: Fix remaining case propagation gaps (partially
  addressed in D5-6-DEMOAUDIT).
  - **Partial fix done** (D5-6-DEMOAUDIT): `CreateCaseActivity` node in
    `vultron/core/behaviors/report/nodes.py` (validate-report BT) now sets
    `to=addressees` and embeds the full `VulnerabilityCase` as `object_`.
    `CreateFinderParticipantNode` now sets `to=[finder_actor_id]`.
  - **Still open**: `EmitCreateCaseActivity` in
    `vultron/core/behaviors/case/nodes.py` (create-case BT) still lacks a
    `to` field and does not embed the full case object. Align this node with
    `report/nodes.py::CreateCaseActivity` or consolidate into one shared node.
  - **Still open (depends on D5-6-AUTOENG)**: The three-actor demo's
    `actor_engages_case()` calls `engage-case` on the case-actor container
    instead of the actor's own container. Once D5-6-AUTOENG auto-engages the
    actor on invite acceptance, this manual call is eliminated entirely.
  - **Spec**: OX-03-001, DEMO-MA-00-001.

#### D5-7 — Project owner sign-off on demo feedback resolution

- [ ] **D5-7**: Project owner sign off. Agents are forbidden from updating
  this task; a human must confirm that all D5-6-* feedback tasks have been
  addressed and the demo meets quality standards prior to completion.

---

### Phase PRIORITY-350 — Maintenance and Tooling (PRIORITY 350)

**Reference**: `plan/PRIORITIES.md` PRIORITY 350

#### TOOLS-1 — Evaluate Python 3.14 compatibility

- [ ] **TOOLS-1**: Evaluate Python 3.14 compatibility. Run the test suite on a
  Python 3.14 branch; if tests pass without issue, update `requires-python` in
  `pyproject.toml` to `>=3.14`, and update docker base images to use Python
  3.14.

#### DOCS-3 — Update `notes/user-stories-trace.md`

- [ ] **DOCS-3**: Update `notes/user-stories-trace.md` (the traceability
  matrix) to map every user story in `docs/topics/user_stories` to the exact
  implementing requirements in `specs/`. Add a mapping for each story and mark
  stories lacking requirement coverage. Add a new section in
  `plan/IMPLEMENTATION_NOTES.md` listing stories with insufficient coverage.

---

### Phase PRIORITY-400 — Replicated Log Synchronization (PRIORITY 400)

**Reference**: `plan/PRIORITIES.md` PRIORITY 400,
`plan/IMPLEMENTATION_NOTES.md` (2026-03-26 SYNC design notes)

These tasks implement distributed append-only case event log replication using
AS2 Announce activities as the transport. The CaseActor (acting as de facto
lead) maintains authoritative case event history and replicates it to
Participant Actors via log synchronization.

> **Design note:** Case Ownership and replication leadership are distinct
> concepts. A future ownership transfer likely implies leadership change,
> but a leadership change alone does not imply an ownership transfer.
>
> `notes/sync-log-replication.md` has been created capturing the RAFT-inspired
> design notes and system invariants. The corresponding entries in
> `plan/IMPLEMENTATION_NOTES.md` have been struck through.

#### SYNC-1 — Local append-only case event log with indexing

- [ ] **SYNC-1**: Implement local append-only case event log with indexing.
  The `CaseEvent` model (`vultron/wire/as2/vocab/objects/case_event.py`)
  provides the foundation. Extend it to a true append-only log with
  hash-chain indexing (each entry carries a content hash and references the
  predecessor hash). Place replication logic in core domain (transport-agnostic
  `CaseEventLog`, `ReplicationState` classes); implement AS2 Announce mappings
  and persistence in adapters. See design notes in `notes/sync-log-replication.md`
  (2026-03-26) for full architectural context.

#### SYNC-2 — One-way log replication to Participant Actors

- [ ] **SYNC-2**: One-way log replication from CaseActor to Participant Actors
  via AS2 Announce activities, with strict conflict handling (reject mismatched
  `prev_log_index`, retry with decremented index). Reconcile "replication
  leadership" with "Case Ownership" (distinct concepts; ownership transfer
  implies leadership change, but not vice versa). Depends on SYNC-1.

#### SYNC-3 — Full sync loop with retry/backoff

- [ ] **SYNC-3**: Full sync loop with retry/backoff. Depends on SYNC-2.

#### SYNC-4 — Multi-peer synchronization

- [ ] **SYNC-4**: Multi-peer synchronization with per-peer replication state.
  Enables RAFT consensus for CaseActor process. Depends on SYNC-3.

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

- [ ] **VOCAB-REG-1**: Research and implement a more robust vocabulary
  registration mechanism that does not rely on developers remembering to
  update `__init__.py` or add class decorators manually. Candidate
  approaches:
  - Dynamic module discovery in the vocabulary subpackage `__init__.py`
    (auto-import all sibling modules)
  - Parent-class/mixin auto-registration on subclass creation
  The registry *structure* and registry *population* are separate concerns
  and may require separate solutions. See `specs/vocabulary-model.md`
  VM-01-005 and the cross-cutting observations in `notes/spec-review-0327.md`.
  **Confirmed still open as of 2026-04-07.**

### EMBARGO-DUR-1 — Update EmbargoPolicy model to ISO 8601 duration format

- [ ] **EMBARGO-DUR-1**: Update the `EmbargoPolicy` Pydantic model in
  `vultron/wire/as2/vocab/objects/embargo_policy.py` to replace the integer
  duration fields (`preferred_duration_days`, `minimum_duration_days`,
  `maximum_duration_days`) with ISO 8601 duration string fields
  (`preferred_duration`, `minimum_duration`, `maximum_duration`) as
  specified in `specs/embargo-policy.md` EP-01-002/003 and
  `specs/duration.md` DUR-01-001.
  - Note: `isodate>=0.7.2` is already a declared dependency in
    `pyproject.toml` — no new package required.
  - Use `datetime.timedelta` internally with an `isodate`-based
    `field_validator`/`field_serializer` pair (see DUR-05-001, DUR-05-002).
  - Update `InitializeDefaultEmbargoNode` in
    `vultron/core/behaviors/case/nodes.py` to parse the ISO 8601 duration
    from the actor's policy (replacing the `preferred_duration_days`
    integer lookup).
  - Add/update unit tests for round-trip serialization and validation.

### FINDER-PART-1 — Create CaseParticipant at report receipt

- [ ] **FINDER-PART-1**: Implement the report-as-proto-case participant
  lifecycle: create a `CaseParticipant` record for the finder at report
  receipt (not deferred to case creation) and retroactively re-link it to
  the case when one is created.
  - Note: `SubmitReportReceivedUseCase` already creates a
    `VultronParticipantStatus` for the finder (with `rm_state=RM.ACCEPTED`)
    as a partial implementation. The full task requires creating a
    `CaseParticipant` domain object with `context` pointing to the
    `VulnerabilityReport` ID.
  - Resolve the open design question in `notes/case-state-model.md`
    ("Report as Proto-Case: Finder Participant Lifecycle") — specifically
    whether finder status belongs in `SubmitReportReceived` (pre-case) or
    `CreateReportReceived` (post-case) — before implementing the full
    `CaseParticipant` creation.
  - At report receipt, create a `CaseParticipant` for the reporter with
    `context` pointing to the `VulnerabilityReport` ID and RM state
    initialized to `RM.RECEIVED`.
  - During case creation (validate-report BT), update the pre-existing
    finder participant's `context` to point to the newly created
    `VulnerabilityCase` ID.
  - See `notes/case-state-model.md` "Report as Proto-Case: Finder Participant
    Lifecycle" for full design rationale.

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
