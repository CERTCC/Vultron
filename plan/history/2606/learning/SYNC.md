---
source: SYNC
timestamp: '2026-06-22T19:33:01.089545+00:00'
title: Isolated two-app replication harness for CaseLogEntry
type: learning
---

For SYNC happy-path replication integration coverage (#901), the most stable
test seam is two isolated FastAPI apps created with `create_isolated_actor_app`
plus a shared `_TestASGIRouter` wired as each app's emitter fallback and as the
module-level default emitter. This setup exercises outbox -> ASGI delivery ->
inbox processing with distinct actor-scoped DataLayers and avoids real HTTP
retry delays.

**Promoted**: 2026-06-22 — captured in `test/AGENTS.md` (SYNC Replication
Test Patterns section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
