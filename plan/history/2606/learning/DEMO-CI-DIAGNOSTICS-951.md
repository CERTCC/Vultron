---
source: DEMO-CI-DIAGNOSTICS-951
timestamp: '2026-06-22T19:34:17.251219+00:00'
title: Inbox logger is uvicorn.error, not module path
type: learning
---

When documenting or grepping container logs for the inbox receipt layer
(Layer 2 of the 3-layer model), the logger is `uvicorn.error` — not the
Python module path `vultron.adapters.driving.fastapi.routers.actors`.
The actors router explicitly overrides the module-default logger with
`logging.getLogger("uvicorn.error")`. Similarly, `PersistLogEntryNode`
uses a class-qualified logger name:
`vultron.core.behaviors.sync.nodes.chain.PersistLogEntryNode` (not the
bare module path). Always verify logger names from source before writing
diagnostic docs or log-filter commands.

**Promoted**: 2026-06-22 — captured in `notes/codebase-structure.md`
(Logger Names: Verify from Source section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
