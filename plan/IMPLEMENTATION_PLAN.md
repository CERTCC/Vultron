# Vultron API v2 Implementation Plan

## Overview

This plan tracks forward-looking work against `specs/*` and
`plan/PRIORITIES.md`. Contains only pending, in-progress, and blocked tasks.

**Completed tasks**: see `plan/IMPLEMENTATION_HISTORY.md` (append-only archive).

**Priority ordering note:** `plan/PRIORITIES.md` is authoritative for project
priority. Section order here groups related work by execution context and MUST
NOT override `plan/PRIORITIES.md` when the two differ.

## PRIORITY-360 — BT Composability Refactoring

**Reference**: `plan/PRIORITIES.md` PRIORITY 360; IDEA-26041703

Can proceed in parallel with PRIORITY-347.

Audit of `vultron/core/behaviors/` identified three composability violations
per `specs/behavior-tree-node-design.md` BTND-02-001 and BTND-03-001:

- [ ] **P360-FIX-1**: Extract `UpdateActorOutbox` duplicate from
  `report/nodes.py` and `case/nodes.py` into a shared node in
  `vultron/core/behaviors/helpers.py`.
  - Both implementations are nearly identical (append `activity_id` to
    actor outbox, call `record_outbox_item`, log the result).
  - Acceptance criterion: One shared `UpdateActorOutbox` in `helpers.py`;
    both domain modules import from `helpers`; all existing tests pass.
  - Per BTND-04-001 (shared module ownership), BTND-02-001 (extract
    duplicates).

- [ ] **P360-FIX-2**: Extract a shared lower-level participant-creation
  helper from `CreateInitialVendorParticipant` (`case/nodes.py:408`) and
  `CreateCaseParticipantNode` (`case/nodes.py:791`).
  - The two nodes have overlapping but non-identical semantics
    (`initial_rm_state` vs fixed `RM.ACCEPTED`; `advance_to_accepted`
    option; `AddParticipantToCaseActivity` emission). Do NOT simply
    replace one with the other.
  - Extract a shared `_create_and_attach_participant()` helper function
    (not a BT node) that handles the DataLayer writes; keep both node
    classes as thin wrappers that add their distinct semantics on top.
  - Acceptance criterion: Both nodes use the shared helper; no
    duplication of DataLayer write logic; all tests pass.
  - Per BTND-02-001 (semantic-preserving consolidation).

- [ ] **P360-FIX-3**: Fix hidden blackboard reads in `RecordCaseCreationEvents`
  (`case/nodes.py:574`) and any other nodes with undeclared blackboard
  access.
  - All blackboard keys read in `update()` or `initialise()` MUST be
    declared via `register_key()` in `setup()`.
  - Audit all nodes in `vultron/core/behaviors/` for this pattern.
  - Acceptance criterion: Every `self.blackboard.get(key)` call is
    preceded by a matching `register_key()` in the same node's `setup()`
    method; py_trees blackboard validation passes without warnings.
  - Per BTND-03-001, BTND-03-002.

---

## PRIORITY-350 — Maintenance and Tooling

**Reference**: `plan/PRIORITIES.md` PRIORITY 350

- [ ] **TOOLS-1**: Evaluate Python 3.14 compatibility. Run the test suite on a
  Python 3.14 branch; if tests pass without issue, update `requires-python`
  in `pyproject.toml` to `>=3.14`, and update docker base images to use
  Python 3.14.

- [ ] **DOCS-3**: Update `notes/user-stories-trace.md` (the traceability
  matrix) to map every user story in `docs/topics/user_stories` to the
  exact implementing requirements in `specs/`. Add a mapping for each story
  and mark stories lacking requirement coverage. Add a new section in
  `plan/IMPLEMENTATION_NOTES.md` listing stories with insufficient coverage.

- [ ] **CONFIG-1**: Replace or supplement JSON/env-var actor configuration
  with YAML config files loaded into validated Pydantic models
  (IDEA-260402-01).
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

## Deferred (Per PRIORITIES.md)

- USE-CASE-01 **`CloseCaseUseCase` wire-type construction** — Replace direct
  construction of `VultronActivity(as_type="Leave")` with domain event
  emission through the `ActivityEmitter` port. Defer until outbound delivery
  integration beyond OX-1.0 is implemented.
- USE-CASE-02 **UseCase Protocol generic enforcement** — Decide on a consistent
  `UseCaseResult` Pydantic return envelope; enforce via mypy. Defer to after
  TECHDEBT-21/22.
- **EP-02/EP-03** — EmbargoPolicy API + compatibility evaluation (`PROD_ONLY`)
- **AR-04/AR-05/AR-06** — Job tracking, pagination, bulk ops (`PROD_ONLY`)
- AGENTIC-00 **Agentic AI integration** (Priority 1000) — out of scope until
  protocol foundation is stable
- FUZZ-00 **Fuzzer node re-implementation** (Priority 500) — see
  `notes/bt-fuzzer-nodes.md`
- IDEA-260402-02 **Per-participant case replica management** — Each Participant
  Actor maintains their own copy of the case object, synchronised from the
  CaseActor via `Announce(CaseLogEntry)` replication. SYNC-1 through SYNC-4
  implement the CaseActor side; the participant-side case replica handler
  (routing inbound `Announce` to the correct local case copy) is part of
  SYNC-2 scope. See `plan/IDEAS.md` IDEA-260402-02 and
  `notes/sync-log-replication.md` for the design.
