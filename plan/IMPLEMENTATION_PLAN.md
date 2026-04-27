# Vultron API v2 Implementation Plan

## Overview

This plan tracks forward-looking work against `specs/*` and
`plan/PRIORITIES.md`. Contains only pending, in-progress, and blocked tasks.

**Completed tasks**: see `plan/IMPLEMENTATION_HISTORY.md` (append-only archive).

**Priority ordering**: `plan/PRIORITIES.md` is authoritative for project
priority. Sections here are organized by topic (see `specs/project-documentation.md`
PD-06). Do not infer priority from section order.

---

## TASK-EMDEFAULT — Default Embargo State

**Source**: `plan/IDEAS.md` IDEA-26041002; spec: `specs/embargo-policy.md` EP-04

When a receiver applies their published default embargo at case creation and
the reporter submitted no explicit counter-proposal, the resulting
`CaseStatus.em_state` MUST be `EM.ACTIVE` (not `EM.PROPOSED`). The current
implementation sets `EM.PROPOSED`, leaving the case in a false limbo state.

### EMDEFAULT.1 — Update `InitializeDefaultEmbargoNode` to produce `EM.ACTIVE`

**Acceptance criteria:**

- After `InitializeDefaultEmbargoNode` runs, `case.current_status.em_state`
  is `EM.ACTIVE`.
- The intermediate `EM.PROPOSED` state is never persisted.
- All tests pass.

**Implementation notes** (see `notes/embargo-default-semantics.md`):

1. In `vultron/core/behaviors/case/nodes.py`
   `InitializeDefaultEmbargoNode.update()`, replace the direct assignment
   `stored_case.current_status.em_state = EM.PROPOSED` with an atomic
   PROPOSE+ACCEPT sequence using `create_em_machine()` and `EMAdapter`.
2. Update tests in
   `test/core/behaviors/case/test_receive_report_case_tree.py` that assert
   `EM.PROPOSED` to assert `EM.ACTIVE`.
3. Check all demo-level integration tests for `EM.PROPOSED` assertions after
   default-embargo initialization and update them.

- [ ] EMDEFAULT.1: Update `InitializeDefaultEmbargoNode` + tests + demo
  assertions (EP-04-001, EP-04-002)

---

## TASK-BTND5 — Generalize Participant BT Nodes

**Source**: `specs/behavior-tree-node-design.md` BTND-05-001 through
BTND-05-003; `specs/configuration.md` CFG-07-001 through CFG-07-004;
`notes/bt-reusability.md` "ActorConfig-Driven Roles" section.

Replace the demo-specific hardcoded participant node (`CreateInitialVendorParticipant`)
with a generalized `CreateCaseOwnerParticipant` driven by actor configuration,
introduce `CVDRoles.CASE_OWNER`, and remove the `CreateFinderParticipantNode`
backward-compat alias.

### BTND5.1 — Add `CVDRoles.CASE_OWNER` to the roles enum

**Acceptance criteria:**

- `CVDRoles.CASE_OWNER` exists in `vultron/core/states/roles.py` as a Flag
  value combinable with VENDOR, COORDINATOR, etc.
- All existing CVDRoles-based tests pass.

- [ ] BTND5.1: Add `CASE_OWNER` flag to `CVDRoles` (BTND-05-001)

### BTND5.2 — Replace `CreateInitialVendorParticipant` with `CreateCaseOwnerParticipant`

**Blocked by BTND5.1.**

**Acceptance criteria:**

- `CreateCaseOwnerParticipant` exists in
  `vultron/core/behaviors/case/nodes.py`; `CreateInitialVendorParticipant` is
  removed.
- Node reads the actor's CVD roles from an `ActorConfig.default_case_roles`
  constructor parameter (no hardcoded `CVDRoles.VENDOR`).
- `CVDRoles.CASE_OWNER` is always included in the created participant's roles
  (appended if not already present).
- All RM-state seeding logic from `CreateInitialVendorParticipant` is
  preserved.
- Unit test: `ActorConfig(default_case_roles=[CVDRoles.COORDINATOR])` →
  participant roles include `COORDINATOR | CASE_OWNER`.

- [ ] BTND5.2a: Implement `ActorConfig` neutral model with `default_case_roles`
  (CFG-07-001, CFG-07-002)
- [ ] BTND5.2b: Implement `CreateCaseOwnerParticipant` + remove
  `CreateInitialVendorParticipant` (BTND-05-002)
- [ ] BTND5.2c: Update `LocalActorConfig` to compose `ActorConfig`
  (CFG-07-003)
- [ ] BTND5.2d: Update all call sites in BT trees to use
  `CreateCaseOwnerParticipant` (CFG-07-004)

### BTND5.3 — Remove `CreateFinderParticipantNode` alias

**Blocked by BTND5.2.**

**Acceptance criteria:**

- `CreateFinderParticipantNode` does not appear anywhere in `vultron/`.
- `from vultron.core.behaviors.case.nodes import CreateFinderParticipantNode`
  raises `ImportError`.

- [ ] BTND5.3: Remove alias + update any remaining call sites (BTND-05-003)

### BTND5.4 — Refactor `CVDRoles` from Flag to `list[StrEnum]`

**Blocked by BTND5.1. Low urgency — schedule after BTND5.3 is complete.**

`CVDRoles` is currently a `Flag` enum (bitmask). Participant records persisted
with flag values are not human-readable. Refactoring to a `list[CVDRoles]`
backed by a `StrEnum` makes persisted records legible (e.g.,
`["vendor", "case_owner"]`) and eliminates bitmask arithmetic at call sites.

**Acceptance criteria:**

- `CVDRoles` is a `StrEnum` (or equivalent) in
  `vultron/core/states/roles.py`.
- `VultronParticipant.case_roles` is typed `list[CVDRoles]`.
- Persisted participant records store role names as strings, not integers.
- All existing tests pass; no bitmask (`|`, `&`) operators remain in
  non-test code referencing `CVDRoles`.
- Existing combination aliases (`FINDER_REPORTER`, etc.) are replaced by
  documented `list` constants or removed.

**References**: BTND-05-001 "Refactor note"; `notes/bt-reusability.md`
"ActorConfig-Driven Roles".

- [ ] BTND5.4: Refactor `CVDRoles` Flag → StrEnum + migrate all call sites

---

## TASK-CC — Cyclomatic Complexity Enforcement

`flake8-mccabe` is already bundled in the project's flake8 install. The
gate integrates into the existing `lint-flake8` CI job and pre-commit
pipeline with no new dependencies. Scope: both `vultron/` and `test/`.

See `plan/IMPLEMENTATION_NOTES.md` section CC-ENFORCEMENT for the full
violation inventory, refactoring guidance, and config change details.

### CC.1 — Phase 1: Reduce CC>15 violations to CC≤10 and activate CC=15 gate

**Prerequisite for CC.2.** Refactor each function below to CC≤10 (the final
target — do not leave them at an intermediate level that will require a
revisit). Once all five are green, activate the flake8 gate in the same PR
so the CI never goes in broken.

**Acceptance criteria:**

- All five functions pass `uv run flake8 --max-complexity=10 --select=C901`
- `.flake8` contains `max-complexity = 15`
- `.pre-commit-config.yaml` has a `flake8` hook entry
- `.github/skills/run-linters/SKILL.md` documents the CC gate
- `lint-flake8` CI job passes with zero C901 warnings

**Dependencies:** none

- [ ] CC.1.1 Reduce `extract_intent` to CC≤10 —
  `vultron/wire/as2/extractor.py:445` (current CC=34). Large conditional
  dispatch chain over (activity type × object type) pairs. Target: extract
  per-type helper functions or a dispatch table keyed on type tuples.
- [ ] CC.1.2 Reduce `rehydrate` to CC≤10 —
  `vultron/wire/as2/rehydration.py:43` (current CC=18)
- [ ] CC.1.3 Reduce `thing2md` to CC≤10 —
  `vultron/scripts/ontology2md.py:33` (current CC=17)
- [ ] CC.1.4 Reduce `mock_datalayer` to CC≤10 —
  `test/core/behaviors/test_performance.py:45` (current CC=17)
- [ ] CC.1.5 Reduce `print_model` to CC≤10 —
  `vultron/core/case_states/make_doc.py:77` (current CC=16)
- [ ] CC.1.6 Activate CC=15 gate: add `max-complexity = 15` to `.flake8`,
  add `flake8` hook to `.pre-commit-config.yaml`, update
  `.github/skills/run-linters/SKILL.md`

### CC.2 — Phase 2: Reduce CC 11–15 violations to CC≤10 and tighten gate

**Blocked by CC.1.**

Refactor the 18 remaining functions at CC 11–15 to CC≤10 (full inventory in
`plan/IMPLEMENTATION_NOTES.md` CC-ENFORCEMENT), then lower `max-complexity`
to 10. Scope: `vultron/` and `test/`.

**Acceptance criteria:**

- All 18 functions pass `uv run flake8 --max-complexity=10 --select=C901`
- `.flake8` contains `max-complexity = 10`
- `lint-flake8` CI job passes with zero C901 warnings

**Dependencies:** CC.1 complete and CI green.

- [ ] CC.2.1 Reduce all 18 CC 11–15 functions to CC≤10 (see
  `plan/IMPLEMENTATION_NOTES.md` CC-ENFORCEMENT for the full list)
- [ ] CC.2.2 Lower `max-complexity` from 15 to 10 in `.flake8`
- [ ] CC.2.3 Upgrade `IMPL-TS-07-008` from SHOULD to MUST in
  `specs/tech-stack.md` now that all CC violations above 10 are resolved

---

## TASK-AF — Activity Factory Functions

**Spec**: `specs/activity-factories.md` (AF-01 through AF-08)
**Notes**: `notes/activity-factories.md`

Introduce a `vultron/wire/as2/factories/` package as the sole public
construction API for outbound Vultron protocol activities. Vultron activity
subclasses in `vocab/activities/` become private implementation details used
only inside factory functions.

**Acceptance criteria:**

- `vultron/wire/as2/factories/` package exists with domain modules
  (`report.py`, `case.py`, `embargo.py`, `case_participant.py`, `actor.py`,
  `sync.py`) and `errors.py`
- All factory functions return plain AS2 base types; ValidationError is
  wrapped in `VultronActivityConstructionError`
- `test/architecture/test_activity_factory_imports.py` passes (no imports of
  `vultron.wire.as2.vocab.activities` outside allowed paths)
- All demo, trigger service, and test call sites migrated to factory functions
- Unused TypeAliases `OfferRef` and `RmInviteToCaseRef` removed;
  `EmProposeEmbargoRef` renamed to `_EmProposeEmbargoRef`
- All linters and tests pass

- [ ] AF.1 Create `vultron/wire/as2/factories/errors.py` with
  `VultronActivityConstructionError(VultronError)`
- [ ] AF.2 Create `factories/report.py` with factory functions for all six
  report activity classes; update `factories/__init__.py`
- [ ] AF.3 Create `factories/case.py` with factory functions for all sixteen
  case activity classes; update `factories/__init__.py`
- [ ] AF.4 Create `factories/embargo.py` with factory functions for all
  eight embargo activity classes; update `factories/__init__.py`
- [ ] AF.5 Create `factories/case_participant.py` with factory functions for
  all five case-participant activity classes; update `factories/__init__.py`
- [ ] AF.6 Create `factories/actor.py` and `factories/sync.py` with factory
  functions for remaining activity classes; update `factories/__init__.py`
- [ ] AF.7 Create `test/architecture/__init__.py` and
  `test/architecture/test_activity_factory_imports.py` (import boundary test)
- [ ] AF.8 Migrate all call sites in demo scripts to factory functions
- [ ] AF.9 Migrate all call sites in trigger use-case modules and adapters
  to factory functions
- [ ] AF.10 Migrate all call sites in test files to factory functions
- [ ] AF.11 Remove unused `OfferRef` and `RmInviteToCaseRef` TypeAliases;
  rename `EmProposeEmbargoRef` → `_EmProposeEmbargoRef`
- [ ] AF.12 Mark internal Vultron activity subclasses as private (prefix
  with `_` or add `__all__` exclusion) in `vocab/activities/` modules
- [ ] AF.13 Add factory functions entry to AGENTS.md quick reference and
  Common Pitfalls

---

## TASK-ARCHVIO — Fix `from_core()` Calls in Core Use Cases

**Background**: `vultron/core/use_cases/received/sync.py` and
`vultron/core/use_cases/triggers/sync.py` call `from_core()` on wire objects
(`CaseLogEntry.from_core(entry)`). This violates ARCH-03-001 — core modules
MUST NOT import from the wire layer. See `notes/activity-factories.md` for
the full analysis.

**The fix**: Move domain→wire translation into a driven adapter or outbox
port adapter. Core use cases should pass domain objects to the adapter; the
adapter calls factory functions (or `from_core()`) to produce wire-format
objects.

**Dependencies**: TASK-AF complete (factories exist before fixing the violation).

- [ ] ARCHVIO.1 Define a driven port interface for domain→wire activity
  translation (in `vultron/core/ports/`)
- [ ] ARCHVIO.2 Implement the adapter in
  `vultron/adapters/driven/activity_translator.py` using factory functions
- [ ] ARCHVIO.3 Replace `from_core()` calls in `sync.py` use cases with
  the new driven adapter injection
- [ ] ARCHVIO.4 Update tests; verify no core module imports wire types

---

## TASK-SR — Spec Registry (YAML + Pydantic)

**Source**: `specs/spec-registry.md` SR-01 through SR-08; `notes/spec-registry.md`  
**Goal**: Convert all `specs/*.md` requirement files to `specs/*.yaml`,
validate them with a Pydantic schema in `vultron/metadata/specs/`, and
provide linting, pytest integration, a pre-commit hook, and context
generation tooling. Stub modules already exist; this task completes the
implementation.

All sub-tasks form a single PR deliverable (one coherent feature unit).

### SR.1 — Complete Pydantic schema and registry loader

- [ ] SR.1.1 Verify `vultron/metadata/specs/schema.py` types are correct
  (discriminated union resolution, `Spec = BehavioralSpec | StatementSpec`
  ordering, `SpecIdStr` pattern)
- [ ] SR.1.2 Verify `vultron/metadata/specs/registry.py` `load_registry()`
  round-trips a minimal YAML fixture without errors
- [ ] SR.1.3 Add `test/metadata/specs/test_schema.py` covering: valid
  `StatementSpec`, valid `BehavioralSpec`, duplicate-ID error, invalid ID
  pattern

### SR.2 — Linter

- [ ] SR.2.1 Implement and test hard-error checks in `lint.py`: duplicate
  IDs, dangling relationships, group/file prefix mismatch
- [ ] SR.2.2 Implement and test advisory-warning checks: `testable: false`
  without steps, rationale > 500 chars, missing tags
- [ ] SR.2.3 Verify `lint_suppress` field suppresses specific warnings
- [ ] SR.2.4 Add `test/metadata/specs/test_lint.py`

### SR.3 — Pytest marker integration

- [ ] SR.3.1 Register `spec` marker in top-level `conftest.py`
- [ ] SR.3.2 Implement `pytest_collection_modifyitems` warning for unknown
  spec IDs (non-blocking)
- [ ] SR.3.3 Add test verifying the warning is emitted for an unknown ID

### SR.4 — Pre-commit hook

- [ ] SR.4.1 Add `spec-lint` hook to `.pre-commit-config.yaml`
  (`pass_filenames: false`, fires on `specs/*.yaml`)

### SR.5 — Context generation tool

- [ ] SR.5.1 Verify `render.py` markdown output matches
  `meta-specifications.md` style
- [ ] SR.5.2 Verify `export_json()` filtering by `kind`, `scope`, `tags`,
  `priority`
- [ ] SR.5.3 Add `test/metadata/specs/test_render.py`

### SR.6 — Migration

**Order matters**: do not delete `.md` files until YAML is validated and
tooling is confirmed working. The `.md` files are the safety net during
migration.

- [ ] SR.6.1 Write a migration script (`tools/migrate_spec_md_to_yaml.py`)
  that converts a single `specs/*.md` file to YAML as a starting point
- [ ] SR.6.2 Migrate all `specs/*.md` files (except `README.md` and
  `meta-specifications.md`) to `specs/*.yaml` — keep `.md` files in place
  during this step
- [ ] SR.6.3 Run `python -m vultron.metadata.specs.lint specs/` — must be
  zero errors before proceeding
- [ ] SR.6.4 Update all in-project skills, prompts, and agent instructions
  that reference `specs/*.md` to use `specs/*.yaml` instead (or the
  context-generation tool output) so dev agents do not break
  - Files to audit: `.github/skills/*/SKILL.md`, `prompts/`,
    `AGENTS.md`, `specs/README.md`, any Copilot instructions that
    mention `specs/` file paths by extension
- [ ] SR.6.5 Update `specs/README.md` and `AGENTS.md` references to reflect
  that specs are now `.yaml`; update the Agent Loading Guide if needed
- [ ] SR.6.6 **Only after SR.6.3–SR.6.5 are complete and verified**: delete
  the original `specs/*.md` requirement files

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
