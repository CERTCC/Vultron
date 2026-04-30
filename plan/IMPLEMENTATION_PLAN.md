# Vultron API v2 Implementation Plan

## Overview

This plan tracks forward-looking work against `specs/*` and
`plan/PRIORITIES.md`. Contains only pending, in-progress, and blocked tasks.

**Completed tasks**: see `plan/history/IMPLEMENTATION_HISTORY.md`
(append-only archive).

**Priority ordering**: `plan/PRIORITIES.md` is authoritative for project
priority. Sections here are organized by topic (see `specs/project-documentation.yaml`
PD-06). Do not infer priority from section order.

---

## TASK-RFC-401 — BTTestScenario Deep-Module Test Harness

**Source**: <https://github.com/CERTCC/Vultron/issues/401>

`test/core/behaviors/report/test_nodes.py` and
`test/core/behaviors/case/test_nodes.py` bypass the
`BTBridge.execute_with_setup()` lifecycle via duplicated
`setup_node_blackboard()` helpers. Introduce `BTTestScenario` in
`test/core/behaviors/bt_harness.py` as the single correct path for all BT
tests (leaf nodes and trees alike).

**Acceptance criteria:**

- `test/core/behaviors/bt_harness.py` exists with `BTTestScenario` class and
  `bt_scenario`, `bt_scenario_factory`, `shared_dl_actors` fixtures.
- No `setup_node_blackboard()` / direct `node.update()` /
  `node.blackboard.register_key()` patterns in `test_nodes.py` files.
- All existing tests pass.

- [ ] RFC-401.1: Create `test/core/behaviors/bt_harness.py`
- [ ] RFC-401.2: Rewrite `test/core/behaviors/report/test_nodes.py` using harness
- [ ] RFC-401.3: Rewrite `test/core/behaviors/case/test_nodes.py` using harness

---

## TASK-CP-CLEANUP — Remove Deprecated `CasePersistence` Compatibility Methods

**Source**: `specs/datalayer.yaml` DL-04-005;
`notes/datalayer-design.md`

**Blocked by TASK-DL-REHYDRATE.**

`CasePersistence` currently still exposes `get()` and `by_type()` as
compatibility methods even though the desired long-term direction is typed
domain-object access via `read()`, `list()`, and dedicated typed helpers.
Remove those deprecated raw-record escape hatches once remaining core callers
have typed replacements.

**Acceptance criteria:**

- `CasePersistence` and `CaseOutboxPersistence` no longer expose `get()` or
  `by_type()`.
- Core callers that currently depend on those methods use `read()`, `list()`,
  or dedicated typed helper methods instead.
- No core code depends on raw `dict[str, Any]` persistence results through the
  narrow ports.
- Specs, notes, and tests are updated consistently.

- [ ] CP-CLEANUP.1: Audit remaining narrow-port `get()` / `by_type()` callers
  in `vultron/core/` and classify the typed replacement needed
- [ ] CP-CLEANUP.2: Add any missing typed query/helper methods needed to
  preserve behavior without raw-record access
- [ ] CP-CLEANUP.3: Remove deprecated `get()` / `by_type()` from
  `CasePersistence` / `CaseOutboxPersistence`; update tests and docs

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

- `CreateCaseOwnerParticipant` reads CVD roles from `ActorConfig.default_case_roles`
  (no hardcoded `CVDRoles.VENDOR`); `CVDRoles.CASE_OWNER` always appended.
- `CreateInitialVendorParticipant` is removed; all RM-state seeding logic preserved.
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

- `CreateFinderParticipantNode` does not appear anywhere in `vultron/`.

- [ ] BTND5.3: Remove alias + update any remaining call sites (BTND-05-003)

### BTND5.4 — Refactor `CVDRoles` from Flag to `list[StrEnum]`

**Blocked by BTND5.1. Low urgency — schedule after BTND5.3.**

`CVDRoles` is a `Flag` enum (bitmask); persisted records are not human-readable.
Refactor to `StrEnum` + `list[CVDRoles]` makes records legible and eliminates
bitmask arithmetic. See `notes/bt-reusability.md` "ActorConfig-Driven Roles".

**Acceptance criteria:**

- `CVDRoles` is a `StrEnum`; `VultronParticipant.case_roles` is `list[CVDRoles]`.
- Persisted records store role names as strings; no bitmask operators in
  non-test code.

- [ ] BTND5.4: Refactor `CVDRoles` Flag → StrEnum + migrate all call sites

---

## TASK-CC — Cyclomatic Complexity Enforcement

`flake8-mccabe` is already bundled in the project's flake8 install. The
gate integrates into the existing `lint-flake8` CI job and pre-commit
pipeline with no new dependencies. Scope: both `vultron/` and `test/`.

See `plan/BUILD_LEARNINGS.md` section CC-ENFORCEMENT for the full
violation inventory, refactoring guidance, and config change details.

### CC.1 — Phase 1: Reduce CC>15 violations to CC≤10 and activate CC=15 gate

**Prerequisite for CC.2.** Refactor each function to CC≤10 (final target —
do not leave at an intermediate level). Activate gate in the same PR.

**Acceptance criteria:**

- All five functions pass `uv run flake8 --max-complexity=10 --select=C901`
- `.flake8` contains `max-complexity = 15`
- `.pre-commit-config.yaml` has a `flake8` hook entry
- `.agents/skills/run-linters/SKILL.md` documents the CC gate

- [ ] CC.1.1 Reduce `extract_intent` CC=34 — `vultron/wire/as2/extractor.py:445`
  (dispatch table keyed on type tuples)
- [ ] CC.1.2 Reduce `rehydrate` CC=18 — `vultron/wire/as2/rehydration.py:43`
- [ ] CC.1.3 Reduce `thing2md` CC=17 — `vultron/scripts/ontology2md.py:33`
- [ ] CC.1.4 Reduce `mock_datalayer` CC=17 — `test/core/behaviors/test_performance.py:45`
- [ ] CC.1.5 Reduce `print_model` CC=16 — `vultron/core/case_states/make_doc.py:77`
- [ ] CC.1.6 Activate CC=15 gate in `.flake8`; add pre-commit hook; update
  run-linters SKILL.md

### CC.2 — Phase 2: Reduce CC 11–15 violations to CC≤10 and tighten gate

**Blocked by CC.1.**

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

- All 21 functions pass `uv run flake8 --max-complexity=10 --select=C901`
- `.flake8` contains `max-complexity = 10`

- [ ] CC.2.1 Reduce all 21 CC 11–15 functions to CC≤10 (see violation list above)
- [ ] CC.2.2 Lower `max-complexity` from 15 to 10 in `.flake8`
- [ ] CC.2.3 Upgrade `IMPLTS-07-008` from SHOULD to MUST in `specs/tech-stack.yaml`

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

- [ ] AF.1 Create `factories/errors.py` with `VultronActivityConstructionError`
- [ ] AF.2 Create `factories/report.py` (6 report activity factory functions)
- [ ] AF.3 Create `factories/case.py` (16 case activity factory functions)
- [ ] AF.4 Create `factories/embargo.py` (8 embargo activity factory functions)
- [ ] AF.5 Create `factories/case_participant.py` (5 functions)
- [ ] AF.6 Create `factories/actor.py` and `factories/sync.py`
- [ ] AF.7 Create `test/architecture/test_activity_factory_imports.py`
- [ ] AF.8–10 Migrate all call sites (demo scripts, trigger use cases, tests)
- [ ] AF.11 Remove unused `OfferRef`/`RmInviteToCaseRef`; rename
  `EmProposeEmbargoRef` → `_EmProposeEmbargoRef`
- [ ] AF.12 Mark internal activity subclasses as private in `vocab/activities/`
- [ ] AF.13 Update AGENTS.md quick reference

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

Introduce `vultron/config.py` with `AppConfig`, `ServerConfig`,
`DatabaseConfig`, `RunMode(StrEnum)`, `get_config()`, `reload_config()`.
Refactor `SeedConfig`/`LocalActorConfig` to `pydantic-settings`.

**Acceptance criteria:**

- `vultron/config.py` exports all above symbols; `RunMode` has `PROTOTYPE`
  and `PROD` values.
- All `os.environ.get()` config reads replaced by `get_config()`.
- `test/test_config.py` covers defaults, env-var override, `reload_config()`.

- [ ] CFG.1 Create `vultron/config.py` (CFG-01-001 through CFG-04-007)
- [ ] CFG.2 Refactor `seed_config.py` to `BaseSettings` (CFG-05-001–CFG-05-003)
- [ ] CFG.3 Replace `os.environ.get()` config reads (CFG-01-004)
- [ ] CFG.4 Add `test/test_config.py` (CFG-06-001–CFG-06-005)

---

## TASK-TRIGCLASS — Trigger Classification and Demo Route Separation

**Source**: `specs/triggerable-behaviors.yaml` TRIG-08, TRIG-09, TRIG-10;
`notes/trigger-classification.md`

**Blocked by TASK-CFG** (needs `RunMode` and `get_config()`).

### TRIGCLASS.1 — Create the demo trigger router

- `demo_triggers.py` with `tags=["Demo Triggers"]` at `/actors/{actor_id}/demo/`.
- `add-note-to-case` and `sync-log-entry` moved from general routers.
- Router conditionally mounted when `RunMode.PROTOTYPE`.

- [ ] TRIGCLASS.1a: Create `demo_triggers.py`; move `add-note-to-case` and
  `sync-log-entry` (TRIG-09-001, TRIG-10-003, TRIG-10-004)
- [ ] TRIGCLASS.1b: Conditionally mount demo router (TRIG-09-002, TRIG-09-003)
- [ ] TRIGCLASS.1c: Add OpenAPI tags (TRIG-09-005)

### TRIGCLASS.2 — Add `add-object-to-case` general trigger

- `POST /actors/{actor_id}/trigger/add-object-to-case` accepts any valid AS2
  object type (TRIG-10-001).
- `add-report-to-case` delegates to it after type-specific validation
  (TRIG-10-002).

- [ ] TRIGCLASS.2: Implement `add-object-to-case`; update `add-report-to-case`

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
- DEMOMA **Multi-actor demo infrastructure** — Core multi-actor demo
  infrastructure is substantially complete (Docker Compose, healthchecks,
  per-actor isolation, trigger-based puppeteering all done; see
  `plan/history/IMPLEMENTATION_HISTORY.md`). Remaining work tracked in
  Vultron#387 (demo log issues noted in D5-7-HUMAN sign-off). See
  `specs/multi-actor-demo.yaml` DEMOMA-01 through DEMOMA-05 and
  `notes/demo-review-26042001.md`. Defer remaining cleanup until
  TASK-TRIGCLASS is complete.
