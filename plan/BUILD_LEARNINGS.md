## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-05-04 ARCHVIO — Fan-out should degrade gracefully when sync_port is absent

When removing the deferred `SyncActivityAdapter` import from `_fan_out_log_entry`,
the initial approach was to raise `VultronError` on `sync_port is None`.  This
broke BT node tests where no sync_port is configured on the blackboard.

Fan-out (`_fan_out_log_entry`) is optional behaviour: when sync_port is absent
(single-actor or test context), skip with a DEBUG log.  Only paths that cannot
proceed without sync_port (`_send_rejection`, `replay_missing_entries_trigger`)
should raise.

The architecture test `test/architecture/test_core_no_adapter_imports.py` uses
AST scanning (same ratchet pattern as `test_activity_factory_imports.py`) to
enforce the boundary going forward.

### 2026-05-05 CC1-MYPY — `VultronActivity.context` was typed wrong in snapshot builder

When extracting `_build_activity_snapshot` from the untyped closure inside
`extract_intent`, mypy correctly flagged that `context=context` passed a raw
`as_Object` to a field typed `NonEmptyString | None`.  The original closure
was invisible to mypy because untyped function bodies are not checked.

Fix: use `_get_id(context)` (consistent with how `origin` is handled).
This converts the AS2 object to its string ID — the semantically correct
value for a snapshot field.

### 2026-05-05 CC1-FLAKY — Pre-existing flaky subtest in test_vultrabot

`test/bt/test_vultrabot.py::MyTestCase::test_main` shows `SUBFAILED` on
`test_main` when run in the full suite but passes in isolation. This is a
pre-existing global-state ordering issue (py_trees blackboard), not caused
by CC.1 changes. Exit code remains 0 because unittest subtest failures do
not trigger pytest's failure exit code.
