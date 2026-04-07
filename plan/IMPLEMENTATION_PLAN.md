# Vultron API v2 Implementation Plan

**Last Updated**: 2026-04-07 (refresh #69: gap analysis, IMPLEMENTATION_NOTES
cleanup, codebase-structure patterns added)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Full details for completed phases are in `plan/IMPLEMENTATION_HISTORY.md`.

**Priority ordering note:** `plan/PRIORITIES.md` is authoritative for project
priority. Section order here groups related work by execution context and MUST
NOT override `plan/PRIORITIES.md` when the two differ.

### Current Status Summary

**Test suite**: Canonical validation last passed on 2026-04-06
(1237 passed, 5581 subtests; `black`, `flake8`, `mypy`, `pyright`, full
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
D5-6-WORKFLOW (all ✅); D5-6-DUP, D5-6-LOGCTX, D5-6-TRIGDELIV,
D5-6-DEMOAUDIT pending; D5-7 pending human sign-off.

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

- [ ] **D5-6-DUP**: Investigate the duplicate VulnerabilityReport warning that
  appears when the vendor processes an incoming `Offer(VulnerabilityReport)`
  (addresses D5-6i from `notes/two-actor-feedback.md`). The vendor logs
  `WARNING: VulnerabilityReport ... already exists` during the first Offer
  processing in a clean demo run, suggesting a double-insert in the
  `SubmitReportReceivedUseCase` handler.
  - Trace the `SubmitReportReceivedUseCase.execute()` path to determine where
    the report object is first persisted and whether it is being saved twice
    (once as part of Offer extraction and again as a separate save).
  - If a double-insert exists: fix the handler to check for existence before
    saving, or deduplicate the save path.
  - If the warning is a false positive (e.g., idempotency guard triggering
    on first run due to demo seeding): clarify the log level (demote to
    DEBUG) and add a code comment explaining the expected behavior.
  - Add a test confirming that processing a single Offer with an embedded
    VulnerabilityReport produces zero duplicate warnings.

#### D5-6-LOGCTX — Improve outbox activity log messages with human-readable context

- [ ] **D5-6-LOGCTX**: Improve log messages for outbox activity queuing and
  delivery so that activity URNs are accompanied by human-readable context
  (addresses D5-6j from `notes/two-actor-feedback.md`). Current logs show
  only `Queued Add activity 'urn:uuid:...'` with no description of what the
  Add contains or why it was queued.
  - Update outbox queuing log messages (in BT nodes and outbox_handler) to
    include the activity type, a summary of the object (e.g., "Add
    CaseParticipant(finder) to Case"), and the reason for queuing (e.g.,
    "finder participant notification").
  - Update `outbox_handler` delivery log messages to include activity type and
    recipient summary when sending to remote inboxes.
  - Apply the same pattern to all BT nodes that queue outbox activities
    (`UpdateActorOutbox`, `CreateFinderParticipantNode`,
    `InitializeDefaultEmbargoNode`).
  - Add tests using `caplog` to verify improved log content.

#### D5-6-TRIGDELIV — Fix trigger endpoints to deliver outbox activities

- [ ] **D5-6-TRIGDELIV**: Ensure all trigger endpoints call `outbox_handler`
  after use-case execution so that activities queued to the actor's outbox
  are actually delivered to recipients (addresses D5-6k from
  `notes/two-actor-feedback.md` and fulfills `specs/outbox.md` OX-03-001/002).
  Currently, trigger endpoints (`trigger_report.py`, `trigger_case.py`,
  `trigger_embargo.py`) execute the use case and return 202, but never
  schedule `outbox_handler` as a BackgroundTask. As a result, activities
  queued by the BT (e.g., `CreateCaseActivity` for finder notification)
  remain in the delivery queue indefinitely unless a subsequent inbox
  delivery happens to drain the queue.
  - Add `BackgroundTasks` dependency to all trigger endpoint functions in
    `trigger_report.py`, `trigger_case.py`, and `trigger_embargo.py`.
  - After use-case execution, schedule `outbox_handler` via
    `background_tasks.add_task(outbox_handler, actor_id, actor_dl, shared_dl)`
    to drain queued activities.
  - Add INFO-level log messages to `outbox_handler` and
    `DeliveryQueueAdapter.emit()` for each delivery attempt so that outbox
    delivery is visible in container logs (complements D5-6k: "logs
    indicating that the outbox delivery is occurring").
  - Add tests verifying that calling a trigger endpoint results in queued
    activities being delivered (mock `outbox_handler` or check that
    `BackgroundTasks.add_task` is called).
  - This is a prerequisite for D5-6-DEMOAUDIT: without trigger→outbox
    delivery, demos cannot rely on triggers to produce end-to-end message
    flow.

#### D5-6-DEMOAUDIT — Audit and refactor all demos for protocol compliance

- [ ] **D5-6-DEMOAUDIT**: Audit all multi-actor demo scripts to ensure they
  reflect the intended protocol flow and do not rely on demo-runner shortcuts
  that would not occur in a real CVD case (addresses D5-6l from
  `notes/two-actor-feedback.md`). This is the most significant remaining
  feedback item: the demo-runner should only trigger primary events
  (submit-report, validate-report, add-note) and then let actor behaviors
  and message exchange play out automatically according to the protocol.
  Depends on D5-6-TRIGDELIV.
  - **Study protocol docs for intended flows**: Review
    `docs/topics/formal_protocol/worked_example.md`,
    `docs/topics/behavior_logic/msg_rm_bt.md`,
    `docs/howto/activitypub/activities/report_vulnerability.md`,
    `docs/howto/activitypub/activities/initialize_case.md`,
    `docs/howto/activitypub/activities/manage_case.md`,
    `docs/howto/activitypub/activities/status_updates.md` and compare
    against demo implementations.
  - **Two-actor demo** (`two_actor_demo.py`): After D5-6-TRIGDELIV, verify
    that the finder actually receives the case notification via outbox
    delivery (not manual injection). Add a verification step that polls the
    finder's datalayer to confirm the case, participant records, and embargo
    are present — proving the full message flow worked end-to-end. Review
    note exchange steps: if possible, use trigger endpoints for adding notes
    rather than manual inbox posts.
  - **Three-actor demo** (`three_actor_demo.py`): Currently uses
    `engage-case` and `propose-embargo` trigger shortcuts where the protocol
    flow should be automatic. After invitation acceptance, the behavior tree
    should handle engagement; after case creation, embargo initialization
    should be automated. Replace trigger shortcuts with proper protocol-driven
    behavior wherever the underlying BT automation supports it. Where the BT
    does not yet automate a step, document the gap and leave the trigger as a
    TODO with a comment explaining what should happen.
  - **Multi-vendor demo** (`multi_vendor_demo.py`): Same analysis as
    three-actor. Replace `validate-report`, `engage-case`, and
    `propose-embargo` trigger shortcuts with protocol-driven flows where
    possible.
  - **Single-actor demos**: These are already protocol-compliant (direct
    activity posts). Verify they remain consistent with the protocol docs and
    do not need changes.
  - **Cross-container verification**: In multi-actor demos, add verification
    steps that confirm the receiving actor has processed the messages and has
    the expected objects in its datalayer (case, participants, embargo). This
    proves the protocol flow works end-to-end, not just that the sender
    queued messages.
  - **Document remaining gaps**: Where the current BT implementation does not
    yet automate a step that the protocol docs describe, document the gap in
    `notes/` or `plan/IMPLEMENTATION_NOTES.md` with a reference to the
    relevant doc section.
  - Add/update demo tests to verify the protocol-compliant flow.

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
