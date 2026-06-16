---
source: ISSUE-970
timestamp: '2026-06-16T14:48:54.847485+00:00'
title: Split FastAPI actors router into focused subpackage
type: implementation
---

## Issue #970 — Split FastAPI actors router module into focused submodules

Converted `vultron/adapters/driving/fastapi/routers/actors.py` (726-line
monolith) into an `actors/` subpackage with three focused submodules:

- `_lookup.py` — actor-record lookup helpers (pure functions, no route handlers)
- `_inbox.py` — inbox processing helpers (`parse_activity`, `_store_*`, etc.)
- `_routes.py` — APIRouter and all `@router.*` endpoint handlers
- `__init__.py` — re-exports `router`, `AnyActor`, `ActorCreateRequest`, `get_shared_dl`

Added 41 focused unit tests in `test/adapters/driving/fastapi/routers/actors/`:
`test_lookup.py` (16 tests) and `test_inbox.py` (25 tests).

All four linters (black, flake8, mypy, pyright) pass. 2945 unit tests pass.

PR: <https://github.com/CERTCC/Vultron/pull/989>
