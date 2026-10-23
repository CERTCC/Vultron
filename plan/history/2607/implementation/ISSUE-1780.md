---
source: ISSUE-1780
timestamp: '2026-07-31T17:09:27.112263+00:00'
title: retire ASGIEmitter — HttpDeliveryAdapter is sole inter-actor delivery path
type: implementation
---

## Issue #1780 — Retire ASGIEmitter; make HTTP the sole inter-actor delivery path

Completed implementation of ADR-0042 / OX-12 compliance work.

**What was done:**

- Deleted `ASGIEmitter` and its reentrancy guard, locality check, mount-prefix stripping
- Added `HttpDeliveryAdapter` as the canonical sole delivery adapter (`http_delivery.py`)
- `demo_http_delivery.py` reduced to backward-compat shim
- Isolated app lifespan no longer creates `app.state.emitter`; production lifespan installs `HttpDeliveryAdapter` via `configure_default_emitter`
- Added ratchet test: no `ASGITransport` or `ASGIEmitter` in `vultron/`
- Deleted ASGI unit tests; upgraded multi-actor test fixtures to use `_TestClientRouter` directly
- `client` fixture upgraded from `_NullDeliveryAdapter` to `_TestClientRouter` with config base_url registration for cc:-to-self loopback
- Full suite: 6910 passed, 265 skipped, 3 xfailed (pre-existing)

PR: <https://github.com/CERTCC/Vultron/pull/1874>
