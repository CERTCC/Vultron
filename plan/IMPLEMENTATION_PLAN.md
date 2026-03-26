# Vultron API v2 Implementation Plan

**Last Updated**: 2026-03-26 (refresh #56: BUGS.md fixes, plan condensed)

## Overview

This plan tracks forward-looking work against `specs/*` and `plan/PRIORITIES.md`.
Full details for completed phases are in `plan/IMPLEMENTATION_HISTORY.md`.

**Priority ordering note:** `plan/PRIORITIES.md` is authoritative for project
priority. Section order here groups related work by execution context and MUST
NOT override `plan/PRIORITIES.md` when the two differ.

### Current Status Summary

**Test suite**: 1026 passed, 5581 subtests (2026-03-26).

All 38 message handlers implemented (including `unknown`). All 9 trigger
endpoints complete. 12 demo scripts, all dockerized in `docker-compose.yml`.
All PRIORITY-30 through PRIORITY-200 phases complete. Active open work:
**PRIORITY-250** (pre-300 cleanup — NAMING-1, SECOPS-1, DOCMAINT-1, REORG-1
remain open; QUALITY-1 done) and **PRIORITY-300** (multi-actor demos; D5-1
unblocked, D5-2 and later blocked by PRIORITY-250).

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

#### NAMING-1 — Standardize wire-layer field naming

- [ ] **NAMING-1**: Audit and migrate all `as_`-prefixed field names in
  `vultron/wire/as2/` to use trailing-underscore convention (e.g.,
  `as_object` → `object_`, `as_type` → `type_`). Class names (e.g.,
  `as_Activity`, `as_Object`) retain the `as_` prefix. Update `specs/`,
  `notes/`, `AGENTS.md`, and documentation to reflect this convention.
  Reference `specs/code-style.md` CS-07-003.

#### SECOPS-1 — Pin GitHub Actions to commit SHAs

- [ ] **SECOPS-1**: Audit all `.github/workflows/` files. Pin every `uses:`
  action reference to a specific commit SHA instead of a version tag. Document
  this as an ADR in `docs/adr/`. Add requirement to `specs/` (a new
  `ci-security.md` or add to `tech-stack.md`).

#### DOCMAINT-1 — Review and update outdated `notes/` files

- [ ] **DOCMAINT-1**: Review all `notes/` files for outdated forward-looking
  statements that have since been implemented. Specifically:
  - (a) Replace concrete "not yet implemented" language with "implemented in
    Phase X" where appropriate.
  - (b) Fix module paths to their canonical current locations (see
    `plan/IMPLEMENTATION_HISTORY.md` phases P60–P75).
  - (c) Mark historical items as such.
  - (d) Identify files that are purely historical and can be removed or
    archived.
  - Files needing particular attention: `notes/state-machine-findings.md`
    (contains fictional commit SHAs and incomplete OPP status markers),
    `notes/datalayer-refactor.md`, `notes/architecture-review.md`,
    `notes/codebase-structure.md`.
  - Cross-reference with `plan/IMPLEMENTATION_HISTORY.md` to verify what
    has been completed.

#### REORG-1 — Reorganize `vultron/core/use_cases/`

- [ ] **REORG-1**: Reorganize `vultron/core/use_cases/` into clearer
  sub-packages separating "received message" handlers from "trigger" handlers.
  The `triggers/` sub-package already captures the latter. Create a
  `received/` sub-package for the former. Keep tests in sync with the
  structure. Document the trigger→received→sync information flow pattern
  (triggers emit messages → received handlers process them → sync replicates
  the resulting case log) in `notes/` and `specs/` where appropriate.

---

### Phase PRIORITY-300 — Multi-Actor Demos (PRIORITY 300)

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
> **Before starting SYNC-1**, create `notes/sync-log-replication.md` capturing
> the RAFT-inspired design notes from `plan/IMPLEMENTATION_NOTES.md`
> (2026-03-26 entry). Remove that entry from `IMPLEMENTATION_NOTES.md` once
> the notes file is committed.

#### SYNC-1 — Local append-only case event log with indexing

- [ ] **SYNC-1**: Implement local append-only case event log with indexing.
  The `CaseEvent` model (`vultron/wire/as2/vocab/objects/case_event.py`)
  provides the foundation. Extend it to a true append-only log with indexed
  lookups. Place replication logic in core domain (transport-agnostic
  `CaseEventLog`, `ReplicationState` classes); implement AS2 Announce mappings
  and persistence in adapters. See design notes in `plan/IMPLEMENTATION_NOTES.md`
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

## Deferred (Per PRIORITIES.md)

- **`CloseCaseUseCase` wire-type construction** — Replace direct construction of
  `VultronActivity(as_type="Leave")` with domain event emission through the
  `ActivityEmitter` port. Defer until outbound delivery integration beyond
  OX-1.0 is implemented.
- **UseCase Protocol generic enforcement** — Decide on a consistent
  `UseCaseResult` Pydantic return envelope; enforce via mypy. Defer to after
  TECHDEBT-21/22.
- **Production readiness** (request validation, idempotency, structured
  logging) — all `PROD_ONLY` or low-priority
- **Response generation** — See `specs/response-format.md` and HISTORY
- **EP-02/EP-03** — EmbargoPolicy API + compatibility evaluation (`PROD_ONLY`)
- **AR-04/AR-05/AR-06** — Job tracking, pagination, bulk ops (`PROD_ONLY`)
- **Domain model separation** (CM-08) — needs ADR; see
  `notes/domain-model-separation.md`
- **Optional BT Refactors (BT-2.2, BT-2.3)** — Wrap `engage_case_handler`
  and `defer_case_handler` in BTs if branching complexity grows; deferred as
  procedural code is adequate for now.
- **Agentic AI integration** (Priority 1000) — out of scope until protocol
  foundation is stable
- **Fuzzer node re-implementation** (Priority 500) — see
  `notes/bt-fuzzer-nodes.md`
