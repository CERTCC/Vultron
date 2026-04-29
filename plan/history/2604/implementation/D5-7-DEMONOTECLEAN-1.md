---
title: "D5-7-DEMONOTECLEAN-1 \u2014 Use trigger API for notes in two-actor\
  \ demo"
type: implementation
date: '2026-04-10'
source: D5-7-DEMONOTECLEAN-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 5539
legacy_heading: "D5-7-DEMONOTECLEAN-1 \u2014 Use trigger API for notes in\
  \ two-actor demo"
date_source: git-blame
---

## D5-7-DEMONOTECLEAN-1 — Use trigger API for notes in two-actor demo

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:5539`
**Canonical date**: 2026-04-10 (git blame)
**Legacy heading**

```text
D5-7-DEMONOTECLEAN-1 — Use trigger API for notes in two-actor demo
```

**Completed**: 2026-04-17

**Summary**: Replaced the two-actor demo's direct inbox POSTs (`Create(Note)` +
`AddNoteToCase`) with proper trigger API calls so that finder notes flow through
the finder's outbox rather than being posted directly to the vendor's inbox.
Vendor replies similarly use the vendor's trigger endpoint.

**Changes**:

- `vultron/core/use_cases/triggers/requests.py`: Added `AddNoteToCaseTriggerRequest`.
- `vultron/core/use_cases/triggers/note.py`: New `SvcAddNoteToCaseUseCase` —
  creates note in DataLayer, adds to local case.notes, queues `Create(Note)` and
  `AddNoteToCase` in actor outbox with `to` populated from case participants.
- `vultron/core/use_cases/triggers/__init__.py`: Exported `SvcAddNoteToCaseUseCase`.
- `vultron/adapters/driving/fastapi/trigger_models.py`: Added `AddNoteToCaseRequest`.
- `vultron/adapters/driving/fastapi/_trigger_adapter.py`: Added `add_note_to_case_trigger`.
- `vultron/adapters/driving/fastapi/routers/trigger_case.py`: Added
  `trigger_add_note_to_case` endpoint at `/{actor_id}/trigger/add-note-to-case`.
- `vultron/demo/two_actor_demo.py`: Rewrote `finder_asks_question` and
  `vendor_replies_to_question` to use trigger endpoints; added
  `wait_for_note_in_case` helper; removed now-unused `AddNoteToCaseActivity`
  and `as_Create` imports.
- `test/core/use_cases/triggers/test_note_trigger.py`: 12 new tests covering note
  creation, DataLayer persistence, outbox queuing, `to` field population, and
  `in_reply_to` handling.
- `test/demo/test_two_actor_demo.py`: Updated test calls to pass new
  `finder_client` parameter to `finder_asks_question`.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1425 passed, 10 skipped, 5581 subtests passed in 83.31s`

---

### D5-7-BTFIX-1 + D5-7-BTFIX-2 — BT cascade violations refactored to proper

subtrees

**Date**: 2026-04-17

**Tasks**: D5-7-BTFIX-1, D5-7-BTFIX-2 (Priority 320)

**Summary**: Eliminated two categories of BT cascade violation (BT-06-005,
BT-06-006) where protocol-observable RM state transitions were triggered
procedurally after `bt.run()` returned rather than as proper BT subtrees.

**Changes**:

- `vultron/core/behaviors/report/nodes.py`: added two new `DataLayerAction`
  nodes — `EmitEngageCaseActivity` (creates `RmEngageCaseActivity`/Join and
  adds to actor outbox) and `EmitDeferCaseActivity` (creates
  `RmDeferCaseActivity`/Leave and adds to actor outbox).
- `vultron/core/behaviors/report/prioritize_tree.py`: added
  `create_prioritize_subtree(case_id, actor_id)` factory. Builds a Selector
  `PrioritizeBT` with an EngagePath (EvaluateCasePriority → EmitEngage →
  TransitionRMtoAccepted) and a DeferPath (EmitDefer →
  TransitionRMtoDeferred).
- `vultron/core/behaviors/report/validate_tree.py`: extended
  `create_validate_report_tree` to accept optional `case_id`/`actor_id`;
  when provided, appends the PrioritizeBT as a child.
- `vultron/core/use_cases/triggers/report.py`: removed `_auto_engage()` from
  `SvcValidateReportUseCase`; passes `case_id`/`actor_id` to validate tree.
- `vultron/core/use_cases/received/case.py`: removed `_auto_engage()` from
  `ValidateCaseUseCase`; passes `case_id`/`actor_id` to validate tree.
- `vultron/core/use_cases/received/actor.py`: replaced procedural
  `SvcEngageCaseUseCase().execute()` call in
  `AcceptInviteActorToCaseReceivedUseCase` with BT bridge execution of a
  `PrioritizeBT` subtree.
- `vultron/core/use_cases/_helpers.py`: promoted `case_addressees()` helper
  from `triggers/_helpers.py` to the core module to break a circular import
  (`nodes.py → triggers._helpers → triggers/__init__ → report.py →
  validate_tree → nodes.py`).
- `notes/bt-integration.md`: updated to document the new PrioritizeBT
  structure and `create_prioritize_subtree` factory.
- Tests: `test/core/behaviors/report/test_prioritize_tree.py` (15 new tests),
  `test/core/behaviors/report/test_validate_tree.py` (updated).

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 new errors (11 pre-existing pyright
  errors in `test_note_trigger.py` unchanged)
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1428 passed, 10 skipped, 5581 subtests passed in 83.60s`
