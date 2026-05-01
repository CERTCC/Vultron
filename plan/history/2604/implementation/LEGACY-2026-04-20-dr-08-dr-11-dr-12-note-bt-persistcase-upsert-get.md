---
title: "DR-08, DR-11, DR-12 \u2014 Note BT, PersistCase upsert, get_failure_reason"
type: implementation
timestamp: '2026-04-20T00:00:00+00:00'
source: LEGACY-2026-04-20-dr-08-dr-11-dr-12-note-bt-persistcase-upsert-get
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7149
legacy_heading: "DR-08, DR-11, DR-12 \u2014 Note BT, PersistCase upsert, get_failure_reason"
date_source: git-blame
---

## DR-08, DR-11, DR-12 — Note BT, PersistCase upsert, get_failure_reason

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7149`
**Canonical date**: 2026-04-20 (git blame)
**Legacy heading**

```text
DR-08, DR-11, DR-12 — Note BT, PersistCase upsert, get_failure_reason
```

**Completed:** DR-08, DR-11, DR-12 (PRIORITY-348 batch)

### DR-08 — `create_note`: AttachNoteToCaseNode BT node

Implemented a full note BT package at `vultron/core/behaviors/note/`:

- `nodes.py`: `SaveNoteNode` (upsert via `dl.save()`) and `AttachNoteToCaseNode`
  (idempotent append of `note_id` to `case.notes`; returns SUCCESS immediately
  when `case_id` is None — standalone notes are valid).
- `create_note_tree.py`: `create_note_tree(note_obj, case_id)` factory returning
  a `Sequence` of `[SaveNoteNode, AttachNoteToCaseNode]`.
- `CreateNoteReceivedUseCase.execute()` rewired to use `BTBridge` +
  `create_note_tree()`; removed `_idempotent_create` usage.
- Key detail: `case_id` comes from `event.note.context` (the Note object's
  context field), not `event.context_id`.

### DR-11 — PersistCase: upsert semantics

Changed `PersistCase.update()` in `vultron/core/behaviors/case/nodes.py` to
call `dl.save()` (upsert) instead of `dl.create()` + `except ValueError`. The
node is now truly idempotent with no warning on duplicate case creation.

### DR-12 — `get_failure_reason(tree)` helper

Added `BTBridge.get_failure_reason(tree)` static method to
`vultron/core/behaviors/bridge.py`. Algorithm: depth-first walk of the tree,
skipping composite nodes (nodes with children), returning the first failing
leaf's `feedback_message` or class name. Returns `""` if no failure is found.
Used in `CreateNoteReceivedUseCase` failure logging.

**Files created:**

- `vultron/core/behaviors/note/__init__.py`
- `vultron/core/behaviors/note/nodes.py`
- `vultron/core/behaviors/note/create_note_tree.py`
- `test/core/behaviors/note/__init__.py`
- `test/core/behaviors/note/conftest.py`
- `test/core/behaviors/note/test_create_note_tree.py` (14 tests)

**Files modified:**

- `vultron/core/behaviors/bridge.py` — added `get_failure_reason`
- `vultron/core/behaviors/case/nodes.py` — `PersistCase` uses `dl.save()`
- `vultron/core/use_cases/received/note.py` — BT-driven execution
- `test/core/behaviors/test_bridge.py` — 4 new `get_failure_reason` tests
- `test/core/use_cases/received/test_note.py` — 2 new attachment tests

**Test Result:**

1706 passed, 12 skipped, 182 deselected, 5581 subtests passed
