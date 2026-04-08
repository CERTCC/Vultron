# Vultron API v2 Implementation Plan

**Last Updated**: 2026-04-08 (D5-6-AUTOENG ✅; SYNC and CLP specs expanded;
canonical validation 1262 passing; three-actor and multi-vendor demos no longer
require manual `engage-case` triggers after invite acceptance)

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
D5-6-DEMOAUDIT ✅; D5-6-AUTOENG ✅; D5-6-NOTECAST ✅; D5-6-CASEPROP ✅;
D5-6-EMBARGORCP ✅; D5-7 pending human sign-off.

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

- [ ] **SYNC-1**: Implement local append-only case event log with indexing and
  the assertion-recording model from `specs/case-log-processing.md` (CLP).
  The `CaseEvent` model (`vultron/wire/as2/vocab/objects/case_event.py`)
  provides the foundation. This task extends it to a true canonical log:

  **CaseLogEntry model** (CLP-02-001 through CLP-02-007, SYNC-01-002):
  - Add `log_index` (monotonically increasing integer, scoped to case)
  - Add `disposition` field: `recorded` | `rejected`
  - Add optional `term` field (Raft term; `null` for single-node deployments)
  - Embed the asserted activity payload as a normalized snapshot (for
    deterministic replay per CLP-02-003)
  - For rejections: add `reason_code` (machine-readable) and optional
    `reason_detail` (human-readable) per CLP-02-005

  **Core domain classes** (transport-agnostic, in `vultron/core/`):
  - `CaseEventLog` — enforces append-only, hash-chain, immutability
  - `ReplicationState` — per-peer last-acknowledged hash

  **Assertion intake** (CLP-01-001 through CLP-01-004):
  - Ordinary inbound case-/proto-case-scoped activities are treated as
    participant assertions (no separate mode marker needed)
  - The CaseActor is the sole emitter of canonical log entries
  - Participant replicas MUST NOT project shared case state from peer
    assertions directly

  **Local audit vs. replicated canonical chain** (CLP-03 through CLP-05):
  - The broader local audit log includes both `recorded` and `rejected`
    `CaseLogEntry` objects
  - The replicated canonical history is a filtered projection of `recorded`
    entries only (CLP-04-001, CLP-04-002)
  - Hash-chain computation is over `recorded` entries only (CLP-04-003)
  - Rejection feedback is sent only to the asserting sender, not broadcast
    to all participants (CLP-05-001, CLP-05-002)

  **Canonical serialization** (SYNC-01-005):
  - Before signing, establish the canonical serialization form for hash
    computation: deterministic key ordering (RFC 8785 JCS), stable UTF-8
    encoding, explicit field inclusion/exclusion, no optional whitespace
  - This is essential for Merkle Tree forward-compatibility
  - See `notes/sync-log-replication.md` "Canonical Serialization" section

  **Adapter responsibilities**:
  - AS2 `Announce` activity mapping for replication transport
  - File/database log storage

  **Leadership guard port** (SYNC-09-003):
  - Add a leadership role-check port to `vultron/core/behaviors/bridge.py`
  - In single-node (SYNC-1–4): the port always returns `True`; imposes zero
    runtime cost but establishes the seam for Phase 3 multi-node

  See design notes in `notes/sync-log-replication.md` and
  `notes/case-log-authority.md` for full architectural context.
  **Specs**: `specs/sync-log-replication.md` SYNC-01, SYNC-08, SYNC-09;
  `specs/case-log-processing.md` CLP-01 through CLP-05.

#### SYNC-2 — One-way log replication to Participant Actors

- [ ] **SYNC-2**: One-way log replication from CaseActor to Participant Actors
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
  - Depends on SYNC-1.

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

> **Design complete** as of 2026-04-08. See `notes/vocabulary-registry.md`
> for full design rationale. Spec updated in `specs/vocabulary-model.md`
> VM-01-001 through VM-01-006. Implementation split into two tasks below.

#### VOCAB-REG-1.1 — Redesign vocabulary registry core mechanics

- [ ] **VOCAB-REG-1.1**: Implement the new registry mechanics in the
  `vultron/wire/as2/vocab/base/` package. Scope: infrastructure only;
  existing decorators remain in place until VOCAB-REG-1.2.
  - Create `vultron/wire/as2/vocab/base/enums.py` with `VocabNamespace`
    enum (`AS`, `VULTRON`)
  - Rewrite `vultron/wire/as2/vocab/base/registry.py`:
    - Replace `Vocabulary(BaseModel)` with a plain
      `VOCABULARY: dict[str, type]` module-level singleton
    - Update `find_in_vocabulary(name: str)` to flat-dict lookup,
      raise `KeyError` on miss; remove the `item_type` parameter
    - Remove `activitystreams_object`, `activitystreams_activity`,
      `activitystreams_link` decorator definitions (they will be
      unused after VOCAB-REG-1.2)
  - Update `vultron/wire/as2/vocab/base/base.py` (`as_Base`):
    - Add `_vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.AS`
    - Add `__init_subclass__` that inspects the new class's `type_`
      annotation; registers the class in `VOCABULARY` under the
      `Literal` value if present, skips otherwise
  - Update `vultron/wire/as2/vocab/objects/base.py` (`VultronObject`):
    - Override `_vocab_ns = VocabNamespace.VULTRON`
  - Add unit tests in `test/wire/as2/vocab/base/`:
    - `__init_subclass__` registers a concrete class (Literal `type_`)
    - `__init_subclass__` skips an abstract class (`str | None` `type_`)
    - `find_in_vocabulary("KnownType")` returns the class
    - `find_in_vocabulary("UnknownType")` raises `KeyError`
    - `VultronObject` subclasses carry `_vocab_ns == VocabNamespace.VULTRON`
  - **Done when**: new unit tests pass; no existing tests broken; the
    old decorator functions are gone from registry.py but decorator
    call sites in vocab class files are not yet touched (that is
    VOCAB-REG-1.2)

#### VOCAB-REG-1.2 — Migrate vocabulary classes and update callers

- [ ] **VOCAB-REG-1.2**: Remove all `@activitystreams_*` decorator usages,
  add startup-guarantee discovery, and update all `find_in_vocabulary()`
  callers. Depends on VOCAB-REG-1.1.
  - Remove `@activitystreams_object` / `@activitystreams_activity` /
    `@activitystreams_link` decorators from all vocab class files
    (≈25 call sites across `vocab/objects/`, `vocab/activities/`,
    `vocab/base/objects/`, `vocab/base/links.py`)
  - Add `pkgutil.iter_modules` + `importlib.import_module` dynamic
    discovery to `vocab/objects/__init__.py` and
    `vocab/activities/__init__.py`
  - Update all five `find_in_vocabulary()` caller files to handle
    `KeyError` instead of `None` returns:
    - `vultron/wire/as2/rehydration.py` — already raises `KeyError`;
      remove the `if cls is None` guard
    - `vultron/adapters/driven/db_record.py` — remove `None` check,
      let `KeyError` propagate
    - `vultron/adapters/driven/datalayer_tinydb.py` — wrap calls in
      `try/except KeyError` to preserve the silent-skip behavior for
      unknown types during list/read
    - `vultron/adapters/driving/fastapi/routers/actors.py` — wrap in
      `try/except KeyError`, continue on miss
    - `vultron/adapters/driving/fastapi/helpers.py` — catch `KeyError`,
      raise `HTTPException(400, ...)`
  - Add a registration completeness test: import both vocab subpackages
    and assert every `.py` module in `vocab/objects/` and
    `vocab/activities/` contributes at least one class to `VOCABULARY`
  - Run the full test suite and confirm it passes
  - **Done when**: no `@activitystreams_*` decorators remain in codebase,
    dynamic discovery is active, all callers updated, completeness test
    passes, full test suite green

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

- [ ] **IDEA-260408-01-1**: Add a DataLayer method (port + TinyDB adapter)
  to look up a `VulnerabilityCase` by its associated `VulnerabilityReport`
  ID.
  - The case links to reports via `VulnerabilityCase.vulnerability_reports:
    list[str]`.
  - Add a method `find_case_by_report_id(report_id: str) ->
    VulnerabilityCase | None` (or similar) to the `DataLayer` Protocol in
    `vultron/core/ports/datalayer.py` and implement in
    `vultron/adapters/driven/datalayer_tinydb.py`.
  - All report-centric use cases (Invalidate, Close, Validate) will use
    this to dereference `report_id → case_id`.
  - Add unit tests for the new DataLayer method.

### IDEA-260408-01-2 — New BT: `receive_report_case_tree`

- [ ] **IDEA-260408-01-2**: Create
  `vultron/core/behaviors/case/receive_report_case_tree.py` with a BT that,
  given a `VulnerabilityReport` ID and actor context, creates:
  - A `VulnerabilityCase` linked to the report
  - A `VultronParticipant` for the reporter with `rm_state=RM.ACCEPTED`
  - A `VultronParticipant` for the receiver with `rm_state=RM.RECEIVED`
  - A default embargo (conditional on no existing embargo)
  - Queues a `Create(Case)` activity to the outbox
  - Migrate the following nodes from `validate_tree.py` into this tree:
    `CreateCaseNode`, `InitializeDefaultEmbargoNode`,
    `CreateInitialVendorParticipant`, `CreateFinderParticipantNode`,
    `CreateCaseActivity`, `UpdateActorOutbox`.
  - Add `test/core/behaviors/case/test_receive_report_case_tree.py`.
  - Depends on IDEA-260408-01-1.

### IDEA-260408-01-3 — Refactor `SubmitReportReceivedUseCase`

- [ ] **IDEA-260408-01-3**: Refactor `SubmitReportReceivedUseCase` in
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

- [ ] **IDEA-260408-01-4**: Remove case/participant/activity nodes from
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

- [ ] **IDEA-260408-01-5**: Update `InvalidateReportReceivedUseCase`,
  `CloseReportReceivedUseCase`, and `ValidateReportReceivedUseCase` to
  dereference `report_id → case_id` using the DataLayer method from
  IDEA-260408-01-1, then delegate to `InvalidateCaseUseCase` /
  `CloseCaseUseCase` / `ValidateCaseUseCase` respectively.
  - Ensures all report-centric protocol activities can locate and update
    the case created at receipt (CM-12-005).
  - Add/update tests verifying the dereference pattern works correctly.
  - Depends on IDEA-260408-01-1.

### IDEA-260408-01-6 — Remove standalone `VultronParticipantStatus` records

- [ ] **IDEA-260408-01-6**: Audit and remove standalone
  `VultronParticipantStatus` record creation in `CreateReport` and
  `AckReport` use cases (if any), as all RM history now lives in
  `VultronParticipant.participant_statuses`.
  - Verify no code path relies on flat `ReportStatus` as the primary RM
    carrier post-case-creation.
  - Depends on IDEA-260408-01-3.

### IDEA-260408-01-7 — Update tests

- [ ] **IDEA-260408-01-7**: Update or remove existing tests that assert case
  creation happens during `ValidateReport` BT execution. Add integration
  test verifying the full flow: `Offer(Report)` receipt creates case →
  `ValidateReport` validates without re-creating case → case is in
  RM.VALID state with correct participants.
  - Depends on IDEA-260408-01-4, IDEA-260408-01-5.

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
