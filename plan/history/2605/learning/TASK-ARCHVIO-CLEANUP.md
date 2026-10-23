---
source: TASK-ARCHVIO-CLEANUP
timestamp: '2026-05-14T20:07:48.050064+00:00'
title: 'ARCH-01-001 sync.py violation fix: SyncActivityPort implementation tasks (cleanup)'
type: learning
---

## Historical task notes removed from notes/architecture-ports-and-adapters.md

The ARCH-01-001 violation in `vultron/core/use_cases/received/sync.py` and
`vultron/core/use_cases/triggers/sync.py` was broader than just `from_core()`
calls. These files also imported wire vocab types and factory functions directly
from the wire layer.

### Implementation tasks that were completed

- ARCHVIO.1: Defined `SyncActivityPort` in `vultron/core/ports/`
- ARCHVIO.2: Implemented `SyncActivityAdapter` in
  `vultron/adapters/driven/sync_activity_adapter.py`
- ARCHVIO.3: Replaced all wire imports in `received/sync.py` and
  `triggers/sync.py` with port calls
- ARCHVIO.4: Updated tests; verified no core module imports wire types in
  these files

### Then-current broader violations list (now largely resolved via #428)

At the time TASK-ARCHVIO was written, other core files still imported from
the wire layer: `behaviors/case/nodes.py`, `behaviors/report/nodes.py`,
`triggers/embargo.py`, `triggers/case.py`, `triggers/actor.py`. These were
subsequently fixed (issue #428 closed 2026-05-06). Remaining violations as of
2026-05-14: `core/behaviors/report/nodes.py`, `core/use_cases/received/actor.py`,
`core/use_cases/received/note.py` — tracked in `specs/architecture.yaml`
ARCH-01-004.

**Promoted**: 2026-05-14 — forward-looking design knowledge retained in
`notes/architecture-ports-and-adapters.md`; historical steps archived here.
