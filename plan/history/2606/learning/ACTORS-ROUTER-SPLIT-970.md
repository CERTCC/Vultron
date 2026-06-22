---
source: ACTORS-ROUTER-SPLIT-970
timestamp: '2026-06-22T19:34:45.573320+00:00'
title: Transport-role naming must stay explicit in adapter paths and classes
type: learning
---

Splitting the FastAPI router under `adapters/driving/fastapi/routers/actors/`
and adding an ASGIEmitter to `adapters/driven/` highlighted the pattern:
adapter names should describe transport role (e.g., `demo_http_delivery`,
`asgi_delivery`) rather than behavior (`delivery_queue`). Behavior-named
adapters create documentation and import drift — readers cannot tell from the
name whether it is inbound or outbound, ASGI or HTTP.

**Promoted**: 2026-06-22 — captured in `AGENTS.md` (Transport-Role Naming pitfall).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
