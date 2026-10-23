---
source: ISSUE-1061
timestamp: '2026-07-08T15:07:37.648921+00:00'
title: Add AS2JSONResponse for AS2 endpoints
type: implementation
---

## Issue #1061 — Add AS2JSONResponse for AS2 endpoints

Implemented `AS2JSONResponse`, a canonical FastAPI `JSONResponse` subclass that
sets `Content-Type: application/activity+json` and serializes `as_Base` instances
with `model_dump(mode="json", by_alias=True, exclude_none=True)`.

### Changes

- Added `vultron/adapters/driving/fastapi/responses.py` with `AS2JSONResponse`
  and `AS2_CONTENT_TYPE` constant (HTTP-09-002, HTTP-09-003).
- Migrated `actors/_routes.py` (`get_actors`, `create_actor`, `get_actor_profile`,
  `get_actor`) to return `AS2JSONResponse`. Fixed missing `mode="json"` in
  `get_actor_profile` that would have crashed on datetime fields.
- Migrated `datalayer.py` (`get_datalayer_contents`, `get_actors`) to return
  `AS2JSONResponse`. Fixed missing `mode="json"` in `get_datalayer_contents`.
- Migrated all 22 routes in `examples.py` to return `AS2JSONResponse`;
  removed `response_model_exclude_none=True` (now handled inside the class).
- Added 7 unit tests: content-type, camelCase serialization, subclass field
  retention (HTTP-08-001 regression), exclude_none, non-AS2 passthrough,
  default and override status codes.

### Outcome

4393 unit tests pass (7 new). Black, flake8, mypy, pyright clean.

PR: <https://github.com/CERTCC/Vultron/pull/1258>
