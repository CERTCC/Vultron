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
