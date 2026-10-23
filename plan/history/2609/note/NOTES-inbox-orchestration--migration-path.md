---
source: NOTES-inbox-orchestration--migration-path
timestamp: '2026-09-17T17:25:23.294640+00:00'
title: Migration Path
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,c) #977 closed; production migrated
**Superseded by:** vultron process_payload path

---

## Migration Path

The existing `InboxPipeline` class and `inbox_handler` function can be
kept temporarily as thin wrappers that delegate to `process_payload` with
production adapters. Once all callers use `process_payload` directly,
the adapter-layer wrappers can be deleted.

See GitHub issue #977 and implementation issue (wired as blocked-by #977)
for task tracking.
