# Vultron API v2 Implementation Plan

**Last Updated**: 2026-03-30 (refresh #61: SPEC-AUDIT-3 complete)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Full details for completed phases are in `plan/IMPLEMENTATION_HISTORY.md`.

**Priority ordering note:** `plan/PRIORITIES.md` is authoritative for project
priority. Section order here groups related work by execution context and MUST
NOT override `plan/PRIORITIES.md` when the two differ.

### Current Status Summary

**Test suite**: 1080 passed, 5581 subtests (2026-03-30).

All 38 message handlers implemented (including `unknown`). All 9 trigger
endpoints complete. 12 demo scripts, all dockerized in `docker-compose.yml`.
All PRIORITY-30 through PRIORITY-200 phases complete.

#### Active open work

**PRIORITY-250** Pre-300 cleanup

- done: NAMING-1, QUALITY-1, SM-GUARD-1, VSR-ERR-1,
BUG-FLAKY-1, REORG-1, SECOPS-1, DOCMAINT-1, SPEC-AUDIT-1, SPEC-AUDIT-2, SPEC-AUDIT-3

**PRIORITY-300** (multi-actor demos; D5-1 unblocked, D5-2 and later blocked
by PRIORITY-250).

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
 — Multi-Actor Demos (PRIORITY 300)

**Reference**: `plan/PRIORITIES.md` PRIORITY 300, `notes/demo-future-ideas.md`

**Note**: D5-1 (architecture review) is unblocked now that PRIORITY-200 is
complete. D5-2 and later are blocked by PRIORITY-250 (pre-300 cleanup).

- [ ] **D5-1**: Confirm the PRIORITY-200 CA-2 follow-up is complete, review
  the current architecture as specified in `specs/` and as implemented in the
  codebase, clarify assumptions for isolated actor/container scenarios, and
  produce a refreshed architectural summary in `notes/` before implementing
  D5-2 and later multi-actor demo scenarios.
- [ ] **D5-2**: Demo Scenario 1 (finder + vendor): Dockerized with two actor
  containers + CaseActor container. **Blocked by PRIORITY-250**.
- [ ] **D5-3**: Demo Scenario 2 (finder + vendor + coordinator). **Blocked by D5-2**.
- [ ] **D5-4**: Demo Scenario 3 (ownership transfer + multi-vendor). **Blocked by D5-3**.
- [ ] **D5-5**: Integration tests and Docker Compose configs for each scenario.
  **Blocked by D5-2**.

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
  All 453 markdown files lint clean.

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
