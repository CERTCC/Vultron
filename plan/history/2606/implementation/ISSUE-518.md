---
source: ISSUE-518
timestamp: '2026-06-02T18:30:59.028880+00:00'
title: Document canonical FastAPI deployment entrypoint
type: implementation
---

## Issue #518 — Document `vultron.adapters.driving.fastapi.main:app` as the canonical deployment entrypoint

Documented `vultron.adapters.driving.fastapi.main:app` as the canonical uvicorn/ASGI deployment entrypoint and clarified that `app_v2` is the mounted sub-application used directly in local development and tests.

Updated onboarding docs in `README.md`, `AGENTS.md`, and `vultron/demo/README.md` to keep startup guidance consistent.

PR: <https://github.com/CERTCC/Vultron/pull/673>
