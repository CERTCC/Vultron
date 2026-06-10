---
source: ISSUE-610
timestamp: '2026-06-01T13:47:54.168664+00:00'
title: Starlette {key:path} for URL-keyed endpoints
type: learning
---

## 2026-05-21 — #610: Starlette path parameter type for URL-keyed endpoints

When a FastAPI/Starlette endpoint needs to accept keys that may contain
forward slashes (e.g., HTTP URL IDs), use `{key:path}` instead of `{key}`.
Register the catch-all route **last** so specific literal routes (e.g.,
`/Offers/`, `/Actors/`) are matched first. The `%2F`-decoding-before-routing
behaviour in Starlette means there is no client-side workaround; only the
server-side `path` converter fixes the root cause.

**Promoted**: 2026-06-01 — captured in `notes/codebase-structure.md`
§ Starlette Path-Type Parameters for URL-Keyed Endpoints and
`vultron/adapters/AGENTS.md` § URL-Keyed IDs in FastAPI Path Segments.
Docs PR: <https://github.com/CERTCC/Vultron/pull/639>.
