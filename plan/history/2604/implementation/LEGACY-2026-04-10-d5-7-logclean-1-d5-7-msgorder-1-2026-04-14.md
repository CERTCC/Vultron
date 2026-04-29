---
title: D5-7-LOGCLEAN-1 + D5-7-MSGORDER-1 (2026-04-14)
type: implementation
date: '2026-04-10'
source: LEGACY-2026-04-10-d5-7-logclean-1-d5-7-msgorder-1-2026-04-14
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 5410
legacy_heading: D5-7-LOGCLEAN-1 + D5-7-MSGORDER-1 (2026-04-14)
date_source: git-blame
legacy_heading_dates:
- '2026-04-14'
---

## D5-7-LOGCLEAN-1 + D5-7-MSGORDER-1 (2026-04-14)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:5410`
**Canonical date**: 2026-04-10 (git blame)
**Legacy heading**

```text
D5-7-LOGCLEAN-1 + D5-7-MSGORDER-1 (2026-04-14)
```

**Legacy heading dates**: 2026-04-14

### D5-7-LOGCLEAN-1 — Replace verbose Pydantic repr in outbox delivery log

Added `_format_object(obj)` helper to `outbox_handler.py` that returns
`"<ClassName> <id>"` for domain objects, passes strings through unchanged, and
handles `None`. Replaced `activity_object` in the INFO delivery log with
`_format_object(activity_object)`, eliminating hundreds of characters of
Pydantic field-repr noise.

**Files changed**:

- `vultron/adapters/driving/fastapi/outbox_handler.py` — added `_format_object`,
  updated delivery log
- `test/adapters/driving/fastapi/test_outbox.py` — added 5 tests covering
  `_format_object` variants and verifying no Pydantic repr in delivery log

### D5-7-MSGORDER-1 — Create(Case) must precede Add(CaseParticipant) in outbox

Reordered BT nodes in `receive_report_case_tree.py` so `CreateCaseActivity` +
`UpdateActorOutbox` run *before* `CreateFinderParticipantNode`. This ensures
the finder receives `Create(Case)` before `Add(CaseParticipant)`, preventing
"case not found" warnings on the finder side. Updated the module docstring to
document the ordering rationale.

**Files changed**:

- `vultron/core/behaviors/case/receive_report_case_tree.py` — reordered
  sequence children, updated docstring
- `test/core/behaviors/case/test_receive_report_case_tree.py` — added
  `test_create_case_precedes_add_participant_in_outbox`

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1399 passed, 10 skipped, 5581 subtests passed in 59.08s`

### D5-7-TRIGNOTIFY-1 — Populate `to` field in all trigger-use-case outbound activities

All trigger use cases that emit outbound state-change activities now populate
the `to` field so that case participants receive the notifications.

**Files changed**:

- `vultron/core/use_cases/triggers/_helpers.py` — added `case_addressees(case,
  excluding_actor_id) -> list[str]` helper; returns all actor IDs from
  `case.actor_participant_index` excluding the triggering actor
- `vultron/core/use_cases/triggers/case.py` — both `SvcEngageCaseUseCase` and
  `SvcDeferCaseUseCase` now pass `to=case_addressees(case, actor_id) or None`
  to `RmEngageCaseActivity` / `RmDeferCaseActivity`
- `vultron/core/use_cases/triggers/embargo.py` — `SvcProposeEmbargoUseCase`,
  `SvcEvaluateEmbargoUseCase`, and `SvcTerminateEmbargoUseCase` now pass
  `to=case_addressees(case, actor_id) or None` to their outbound activities
- `vultron/core/use_cases/triggers/report.py` — added `_report_addressees()`
  helper (looks up case via `find_case_by_report_id`, falls back to offer
  actor); `SvcInvalidateReportUseCase`, `SvcRejectReportUseCase`, and
  `SvcCloseReportUseCase` now pass `to=_report_addressees(...)`; added
  `is_case_model` guard to fix mypy type error
- `test/core/use_cases/triggers/__init__.py` — new empty init
- `test/core/use_cases/triggers/conftest.py` — vocab registry import
- `test/core/use_cases/triggers/test_trignotify.py` — 10 new tests covering
  all trigger use cases; verify `to` is populated, contains the other
  participant, and excludes the triggering actor

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1409 passed, 10 skipped, 5581 subtests passed in 69.59s`
