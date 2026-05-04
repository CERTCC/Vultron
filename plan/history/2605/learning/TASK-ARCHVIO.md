---
source: TASK-ARCHVIO
timestamp: '2026-05-04T18:02:08.461765+00:00'
title: Sync use cases violate ARCH-01-001 more broadly than from_core() alone
type: learning
---

TASK-ARCHVIO was scoped to "fix `from_core()` calls in core use cases." But
the real ARCH-01-001 violation in `received/sync.py` and `triggers/sync.py`
goes deeper: these files import both wire vocab types (`CaseLogEntry`,
`WireCaseLogEntry`) and factory functions from `vultron.wire.as2.factories`.
Fixing only `from_core()` while leaving wire factory imports in core still
violates ARCH-01-001.

Incremental fix: introduce a narrow driven port `SyncActivityPort` with
`send_reject_log_entry()` and `send_announce_log_entry()` methods.
The adapter (`SyncActivityAdapter`) owns the full domain->wire->persist->outbox
pipeline. Core use cases call the port with domain objects only.

Long-term architecture: replace procedural sync use-case logic with a behavior
tree (via BTBridge). BT leaf nodes use `SyncActivityPort` for outbound actions.
This matches how other protocol flows (report, case, embargo) already work.
The BT integration is a separate future task; it depends on ARCHVIO completing
the port first.

Additionally, many other core files still import from the wire layer
(behaviors/case/nodes.py, behaviors/report/nodes.py, triggers/embargo.py,
triggers/case.py, triggers/actor.py, etc.). These are separate ARCH-01-001
violations that each need their own driven port or ActivityEmitter expansion.

**Promoted**: 2026-05-04 — captured in notes/architecture-ports-and-adapters.md
"Sync Use-Case Architecture" section.
