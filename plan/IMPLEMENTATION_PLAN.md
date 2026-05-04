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

## TASK-TRIGCLASS — Trigger Classification and Demo Route Separation

**Source**: `specs/triggerable-behaviors.yaml` TRIG-08, TRIG-09, TRIG-10;
`notes/trigger-classification.md`

**Requires `RunMode` and `get_config()` from `vultron/config.py` (now available).**

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
