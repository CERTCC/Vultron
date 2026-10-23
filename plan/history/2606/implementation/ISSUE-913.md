---
source: ISSUE-913
timestamp: '2026-06-15T18:20:59.751388+00:00'
title: Add tests for add_note_to_case_trigger_bt (BTND-07 note/sender migration)
type: implementation
---

## Issue #913 — Migrate note and sender BT areas to BTND-07 structure

The structural BTND-07 migration (flat `nodes.py` → `nodes/` subpackage) for
`vultron/core/behaviors/note/` and `vultron/core/behaviors/sender/` was
completed in PR #917 (issue #883). Issue #913 remained open because
`add_note_to_case_trigger_bt()` in `add_note_trigger_tree.py` had no
dedicated tests.

Added `test/core/behaviors/note/test_add_note_trigger_tree.py` with 7 tests
covering:

- Tree structure (name, 3 children, correct types)
- Success path: note created, attached to case, activity queued to outbox
- `result_out` populated with `note_id` and `note_dict` on success
- Failure when trigger factory absent
- Failure when no CASE_MANAGER participant, with assertion documenting
  expected partial-write behavior (note attached locally even though send fails)
- `in_reply_to` forwarding verified in `note_dict["inReplyTo"]`

All 3243 unit tests pass. Black, flake8, mypy, pyright clean.

PR: [#964](https://github.com/CERTCC/Vultron/pull/964)
