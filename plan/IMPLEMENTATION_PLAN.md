# Vultron API v2 Implementation Plan

## Overview

This plan tracks forward-looking work against `specs/*` and
`plan/PRIORITIES.md`. Contains only pending, in-progress, and blocked tasks.

**Completed tasks**: see `plan/IMPLEMENTATION_HISTORY.md` (append-only archive).

**Priority ordering note:** `plan/PRIORITIES.md` is authoritative for project
priority. Section order here groups related work by execution context and MUST
NOT override `plan/PRIORITIES.md` when the two differ.

---

## Priority 450: Cyclomatic Complexity Enforcement

`flake8-mccabe` is already bundled in the project's flake8 install. The
gate integrates into the existing `lint-flake8` CI job and pre-commit
pipeline with no new dependencies. Scope: both `vultron/` and `test/`.

See `plan/IMPLEMENTATION_NOTES.md` section CC-ENFORCEMENT for the full
violation inventory, refactoring guidance, and config change details.

### CC-1 — Phase 1: Reduce CC>15 violations to CC≤10 and activate CC=15 gate

**Prerequisite for CC-2.** Refactor each function below to CC≤10 (the final
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

- [ ] CC-1.1 Reduce `extract_intent` to CC≤10 —
  `vultron/wire/as2/extractor.py:445` (current CC=34). Large conditional
  dispatch chain over (activity type × object type) pairs. Target: extract
  per-type helper functions or a dispatch table keyed on type tuples.
- [ ] CC-1.2 Reduce `rehydrate` to CC≤10 —
  `vultron/wire/as2/rehydration.py:43` (current CC=18)
- [ ] CC-1.3 Reduce `thing2md` to CC≤10 —
  `vultron/scripts/ontology2md.py:33` (current CC=17)
- [ ] CC-1.4 Reduce `mock_datalayer` to CC≤10 —
  `test/core/behaviors/test_performance.py:45` (current CC=17)
- [ ] CC-1.5 Reduce `print_model` to CC≤10 —
  `vultron/core/case_states/make_doc.py:77` (current CC=16)
- [ ] CC-1.6 Activate CC=15 gate: add `max-complexity = 15` to `.flake8`,
  add `flake8` hook to `.pre-commit-config.yaml`, update
  `.github/skills/run-linters/SKILL.md`

### CC-2 — Phase 2: Reduce CC 11–15 violations to CC≤10 and tighten gate

**Blocked by CC-1.**

Refactor the 18 remaining functions at CC 11–15 to CC≤10 (full inventory in
`plan/IMPLEMENTATION_NOTES.md` CC-ENFORCEMENT), then lower `max-complexity`
to 10. Scope: `vultron/` and `test/`.

**Acceptance criteria:**

- All 18 functions pass `uv run flake8 --max-complexity=10 --select=C901`
- `.flake8` contains `max-complexity = 10`
- `lint-flake8` CI job passes with zero C901 warnings

**Dependencies:** CC-1 complete and CI green.

- [ ] CC-2.1 Reduce all 18 CC 11–15 functions to CC≤10 (see
  `plan/IMPLEMENTATION_NOTES.md` CC-ENFORCEMENT for the full list)
- [ ] CC-2.2 Lower `max-complexity` from 15 to 10 in `.flake8`
- [ ] CC-2.3 Upgrade `IMPL-TS-07-008` from SHOULD to MUST in
  `specs/tech-stack.md` now that all CC violations above 10 are resolved

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
