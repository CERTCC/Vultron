# Vultron API v2 Implementation Plan

## Overview

This plan tracks forward-looking work against `specs/*` and
`plan/PRIORITIES.md`. Contains only pending, in-progress, and blocked tasks.

**Completed tasks**: see `plan/IMPLEMENTATION_HISTORY.md` (append-only archive).

**Priority ordering**: `plan/PRIORITIES.md` is authoritative for project
priority. Sections here are organized by topic (see `specs/project-documentation.yaml`
PD-06). Do not infer priority from section order.

---

## TASK-EMDEFAULT — Default Embargo State

**Source**: `plan/IDEAS.md` IDEA-26041002; spec: `specs/embargo-policy.yaml` EP-04

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

**Source**: `specs/behavior-tree-node-design.yaml` BTND-05-001 through
BTND-05-003; `specs/configuration.yaml` CFG-07-001 through CFG-07-004;
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

See `plan/BUILD_LEARNINGS.md` section CC-ENFORCEMENT for the full
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
- `.agents/skills/run-linters/SKILL.md` documents the CC gate
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
  `.agents/skills/run-linters/SKILL.md`

### CC.2 — Phase 2: Reduce CC 11–15 violations to CC≤10 and tighten gate

**Blocked by CC.1.**

Refactor the 21 remaining functions at CC 11–15 to CC≤10, then lower
`max-complexity` to 10. Scope: `vultron/` and `test/`.

Current violations (CC 11–15):

- `vultron/adapters/driving/fastapi/main.py` `main` CC=11
- `vultron/adapters/driving/fastapi/routers/actors.py` `post_actor_inbox` CC=12
- `vultron/core/behaviors/case/nodes.py` `CreateInitialVendorParticipant.update` CC=12
- `vultron/core/behaviors/case/nodes.py` `InitializeDefaultEmbargoNode.update` CC=13
- `vultron/core/behaviors/case/nodes.py` `CreateCaseParticipantNode.update` CC=13
- `vultron/core/behaviors/report/nodes.py` `CreateCaseActivity.update` CC=15
- `vultron/core/case_states/validations.py` `is_valid_transition` CC=13
- `vultron/core/use_cases/received/embargo.py` `RemoveEmbargoEventFromCaseReceivedUseCase.execute` CC=11
- `vultron/core/use_cases/received/embargo.py` `AcceptInviteToEmbargoOnCaseReceivedUseCase.execute` CC=15
- `vultron/core/use_cases/received/report.py` `SubmitReportReceivedUseCase.execute` CC=14
- `vultron/core/use_cases/received/status.py` `AddCaseStatusToCaseReceivedUseCase.execute` CC=11
- `vultron/core/use_cases/triggers/embargo.py` `SvcAcceptEmbargoUseCase.execute` CC=13
- `vultron/core/use_cases/triggers/embargo.py` `SvcRejectEmbargoUseCase.execute` CC=12
- `vultron/demo/scenario/multi_vendor_demo.py` `verify_multi_vendor_case_state` CC=13
- `vultron/demo/scenario/three_actor_demo.py` `verify_case_actor_case_state` CC=12
- `vultron/demo/scenario/two_actor_demo.py` `find_case_for_offer` CC=11
- `vultron/demo/scenario/two_actor_demo.py` `verify_vendor_case_state` CC=13
- `vultron/metadata/specs/llm_export.py` `to_llm_json` CC=13
- `vultron/metadata/specs/render.py` `render_markdown` CC=14
- `vultron/metadata/specs/render.py` `_spec_to_dict` CC=12
- `vultron/wire/as2/extractor.py` `ActivityPattern.match` CC=13

**Acceptance criteria:**

- All 18 functions pass `uv run flake8 --max-complexity=10 --select=C901`
- `.flake8` contains `max-complexity = 10`
- `lint-flake8` CI job passes with zero C901 warnings

**Dependencies:** CC.1 complete and CI green.

- [ ] CC.2.1 Reduce all 21 CC 11–15 functions to CC≤10 (see violation
  list above)
- [ ] CC.2.2 Lower `max-complexity` from 15 to 10 in `.flake8`
- [ ] CC.2.3 Upgrade `IMPLTS-07-008` from SHOULD to MUST in
  `specs/tech-stack.yaml` now that all CC violations above 10 are resolved

---

## TASK-AF — Activity Factory Functions

**Spec**: `specs/activity-factories.yaml` (AF-01 through AF-08)
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

## TASK-CFG — Unified Configuration System

**Source**: `specs/configuration.yaml` CFG-01 through CFG-07;
`notes/configuration.md`

Introduce `vultron/config.py` as the single unified configuration API for the
application. This neutral module (no adapter or wire imports) provides
`AppConfig`, `ServerConfig`, `DatabaseConfig`, `RunMode(StrEnum)`,
`get_config()`, and `reload_config()`. Env-var override uses `VULTRON_` prefix
with `__` nesting. Also refactor `SeedConfig`/`LocalActorConfig` in
`vultron/demo/seed_config.py` to `pydantic-settings` `BaseSettings`.

**Acceptance criteria:**

- `vultron/config.py` exports `AppConfig`, `ServerConfig`, `DatabaseConfig`,
  `RunMode`, `get_config()`, `reload_config()`.
- `RunMode` is a `StrEnum` with at minimum `PROTOTYPE` and `PROD` values.
- `ServerConfig.run_mode` defaults to `RunMode.PROTOTYPE`.
- All `os.environ.get()` calls for Vultron config replaced by `get_config()`
  access or `Depends(get_config)` in FastAPI endpoints.
- `SeedConfig` and `LocalActorConfig` in `vultron/demo/seed_config.py`
  refactored to use `pydantic-settings`.
- Tests: `test/test_config.py` covers defaults, env-var override, and
  `reload_config()` invalidation.

- [ ] CFG.1 Create `vultron/config.py` with `AppConfig`, `ServerConfig`,
  `DatabaseConfig`, `RunMode`, `get_config()`, `reload_config()` using
  `pydantic-settings` and YAML source (CFG-01-001 through CFG-04-007)
- [ ] CFG.2 Refactor `vultron/demo/seed_config.py` `SeedConfig` and
  `LocalActorConfig` to `BaseSettings`; preserve existing public API
  (CFG-05-001 through CFG-05-003)
- [ ] CFG.3 Replace all `os.environ.get()` config reads in adapter and demo
  code with `get_config()` (CFG-01-004)
- [ ] CFG.4 Add `test/test_config.py` unit tests for defaults, env-var
  override, and YAML loading (CFG-06-001 through CFG-06-005)

---

## TASK-TRIGCLASS — Trigger Classification and Demo Route Separation

**Source**: `specs/triggerable-behaviors.yaml` TRIG-08, TRIG-09, TRIG-10;
`notes/trigger-classification.md`

**Blocked by TASK-CFG** (needs `RunMode` enum and `get_config()`).

Introduce a formal classification of trigger endpoints into *general-purpose*
and *demo-only* categories, with separate URL prefixes and conditional router
mounting based on `RunMode`.

### TRIGCLASS.1 — Create the demo trigger router

**Acceptance criteria:**

- `vultron/adapters/driving/fastapi/routers/demo_triggers.py` exists with
  `tags=["Demo Triggers"]` and path prefix `/actors/{actor_id}/demo/`.
- `add-note-to-case` moved from `trigger_case.py` to `demo_triggers.py` at
  `POST /actors/{actor_id}/demo/add-note-to-case` (TRIG-10-003).
- `sync-log-entry` moved from `trigger_sync.py` to `demo_triggers.py` at
  `POST /actors/{actor_id}/demo/sync-log-entry` (TRIG-10-004).
- Demo router is conditionally mounted in `v2_router.py` only when
  `get_config().server.run_mode == RunMode.PROTOTYPE` (TRIG-09-002).

- [ ] TRIGCLASS.1a: Create `demo_triggers.py` router; move `add-note-to-case`
  and `sync-log-entry` (TRIG-09-001, TRIG-10-003, TRIG-10-004)
- [ ] TRIGCLASS.1b: Conditionally mount demo router in `v2_router.py` based
  on `RunMode` (TRIG-09-002, TRIG-09-003)
- [ ] TRIGCLASS.1c: Add OpenAPI tags to distinguish demo vs general triggers
  (TRIG-09-005)

### TRIGCLASS.2 — Add `add-object-to-case` general trigger

**Acceptance criteria:**

- `POST /actors/{actor_id}/trigger/add-object-to-case` exists in
  `trigger_case.py`; accepts any valid AS2 object type as `object` in the
  request body (TRIG-10-001).
- `add-report-to-case` delegates to `add-object-to-case` after type-specific
  validation (TRIG-10-002).
- Unit tests cover both endpoints.

- [ ] TRIGCLASS.2: Implement `add-object-to-case` trigger; update
  `add-report-to-case` to delegate to it (TRIG-10-001, TRIG-10-002)

---

## TASK-OUTBOX-TO — Outbox `to:` Field Enforcement

**Source**: `specs/outbox.yaml` OX-08-001, OX-08-002, OX-08-004;
`notes/outbox.md`

All outbound Vultron activities are direct messages and MUST have a non-empty
`to:` field. Enforce this at `handle_outbox_item` so no activity can leave the
outbox without an addressee.

**Acceptance criteria:**

- `VultronOutboxToFieldMissingError(VultronError)` exists in `vultron/errors.py`
  with `activity_id` and `activity_type` attributes.
- `handle_outbox_item` in `vultron/adapters/driving/fastapi/outbox_handler.py`
  raises `VultronOutboxToFieldMissingError` when `to:` is absent or an empty
  list; logs `WARNING` when `cc`/`bto`/`bcc` are non-empty.
- Existing `VultronOutboxObjectIntegrityError` check is unmodified.
- Unit tests cover the missing-`to:` raise and the `cc`/`bto`/`bcc` warning
  branches.

- [ ] OUTBOX-TO.1 Add `VultronOutboxToFieldMissingError` to `vultron/errors.py`
  (OX-08-001, OX-08-002)
- [ ] OUTBOX-TO.2 Add `to:` presence check and `cc`/`bto`/`bcc` warning to
  `handle_outbox_item` (OX-08-001, OX-08-002, OX-08-004)
- [ ] OUTBOX-TO.3 Add unit tests for both branches

---

## TASK-DL-REHYDRATE — DataLayer Auto-Rehydration on Read

**Source**: `specs/datalayer.yaml` DL-01-001 through DL-01-004, DL-02-001;
`notes/datalayer-design.md`

**Note**: Shares implementation context with TASK-ARCHVIO — once auto-rehydration
is in the adapter, the manual coercion that ARCHVIO.3 removes becomes visible.
These tasks may be batched into a single PR.

`dl.read()` and `dl.list(type_key)` MUST return fully rehydrated, typed
domain objects. Currently the SQLite/TinyDB adapters return dehydrated records
requiring manual `model_validate` coercion in use cases.

**Acceptance criteria:**

- `DataLayer` port has a `list(type_key: str) -> Iterable[PersistableModel]`
  method (DL-01-002).
- `dl.read(id)` returns a fully rehydrated typed object; bare string
  references in nested fields (`object_`, `target`, `origin`) are expanded
  (DL-01-001, DL-01-003).
- Core use cases contain no `model_validate(dl.read(...))`, no
  `record_to_object()`, and no `isinstance(result, Document)` checks
  (DL-01-004).
- `dl.save(obj)` upserts by `id_`: saving the same object twice produces the
  same stored state (DL-02-002).
- All existing tests pass.

- [ ] DL-REHYDRATE.1 Add `list(type_key)` to `DataLayer` Protocol and both
  adapter implementations (DL-01-002)
- [ ] DL-REHYDRATE.2 Implement auto-rehydration in `datalayer_sqlite.py`
  `read()` and `list()` (DL-01-001, DL-01-003)
- [ ] DL-REHYDRATE.3 Implement auto-rehydration in `datalayer_tinydb.py`
  `read()` and `list()` (DL-01-001, DL-01-003)
- [ ] DL-REHYDRATE.4 Remove manual `model_validate` / `record_to_object()`
  coercion from all core use cases (DL-01-004)
- [ ] DL-REHYDRATE.5 Add tests confirming auto-rehydration and upsert
  idempotency

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
- SYNC-1–SYNC-4 **Per-participant case replica / sync-log replication** —
  Each Participant Actor maintains their own copy of the case object,
  synchronised from the CaseActor via `Announce(CaseLogEntry)` replication.
  See `specs/sync-log-replication.yaml` and `notes/sync-log-replication.md`.
  Defer until the outbox delivery pipeline (OX-03, OX-04) is stable.
- DEMOMA **Multi-actor demo infrastructure** — Docker Compose healthchecks per
  actor, per-actor isolation, acceptance tests asserting RM/EM/CS end-state.
  See `specs/multi-actor-demo.yaml` DEMOMA-01 through DEMOMA-05 and
  `notes/demo-review-26042001.md`. Defer until TASK-TRIGCLASS and
  TASK-DL-REHYDRATE are complete.
