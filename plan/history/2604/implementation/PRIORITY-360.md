---
title: "PRIORITY-360 \u2014 BT Composability Refactoring (Completed)"
type: implementation
date: '2026-04-23'
source: PRIORITY-360
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7915
legacy_heading: "PRIORITY-360 \u2014 BT Composability Refactoring (Completed)"
date_source: git-blame
---

## PRIORITY-360 — BT Composability Refactoring (Completed)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7915`
**Canonical date**: 2026-04-23 (git blame)
**Legacy heading**

```text
PRIORITY-360 — BT Composability Refactoring (Completed)
```

**Reference**: `plan/PRIORITIES.md` PRIORITY 360; IDEA-26041703

Implemented all three composability fixes identified by the prior audit:

### P360-FIX-1 — Extract shared `UpdateActorOutbox` to `helpers.py`

- Added canonical `UpdateActorOutbox` class to
  `vultron/core/behaviors/helpers.py` with full `setup()`/`update()`
  implementation using the `has_outbox` protocol check.
- Removed near-identical duplicate class definitions from
  `vultron/core/behaviors/report/nodes.py` (~88 lines) and
  `vultron/core/behaviors/case/nodes.py` (~65 lines).
- Both domain modules now re-export `UpdateActorOutbox` from `helpers` with
  `# noqa: F401` for backward compatibility.
- All existing callers importing from `report.nodes` or `case.nodes` continue
  to work without changes.

### P360-FIX-2 — Extract `_create_and_attach_participant()` helper

- Extracted a module-private `_create_and_attach_participant(dl, participant,
  case_id, actor_id_for_index, node_logger) -> CaseModel | None` helper in
  `case/nodes.py` before `CreateInitialVendorParticipant`.
- Helper handles the common DataLayer writes: idempotent participant creation,
  `case_participants` list update, and `actor_participant_index` update.
- Returns an **unsaved** `CaseModel` so each caller can perform its distinct
  mutations (RM advancement, `record_event`) before calling `dl.save()`.
- Both `CreateInitialVendorParticipant.update()` and
  `CreateCaseParticipantNode.update()` refactored to use the shared helper.

### P360-FIX-3 — Register `"activity"` key in `RecordCaseCreationEvents.setup()`

- Added `self.blackboard.register_key("activity", access=READ)` to
  `RecordCaseCreationEvents.setup()`.
- Replaced the previous `py_trees.blackboard.Blackboard.storage` global dict
  access in `update()` with `try/except KeyError` on
  `self.blackboard.get("activity")`.
- The optional key is handled correctly: absent key raises `KeyError` (not
  `AttributeError`), and the node treats absence as "no activity to record".

### Tests

- Added `test/core/behaviors/case/test_nodes.py` with 20 tests covering:
  - P360-FIX-1: `UpdateActorOutbox` in `helpers.py` is importable from both
    domain modules (backward compatibility) and appends to actor outbox.
  - P360-FIX-2: shared helper creates participant, attaches to case, and
    returns unsaved case; both node callers save with their distinct mutations.
  - P360-FIX-3: `"activity"` key registered in `setup()`; accessing unset
    registered key raises `KeyError`; node records events correctly with/without
    activity on blackboard.
- All 1812 unit tests pass; all four linters (Black, flake8, mypy, pyright)
  clean.
