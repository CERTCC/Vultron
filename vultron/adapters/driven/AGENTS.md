# Driven Adapters — Design Rules

## HTTP Delivery Design Rules (ADR-0042, OX-12)

`HttpDeliveryAdapter` is the sole inter-actor delivery adapter. Every
recipient — co-located or remote — receives activities via HTTP POST to
`{actor_uri}/inbox/` (OX-12-001). There is no in-process ASGI shortcut.

**Application code MUST NOT construct `httpx.ASGITransport` directly.**
The only permitted use is FastAPI's `TestClient`, which uses `ASGITransport`
internally to drive a *single* application's own endpoints; that is the
standard FastAPI test tool and is not an inter-actor delivery mechanism
(OX-12-003). See `test/architecture/test_no_asgi_transport_in_app_code.py`.

> **Historical note:** a previous `ASGIEmitter` adapter delivered to
> co-located actors in-process. It was retired by ADR-0042 because it masked
> inter-actor delivery bugs and required accidental complexity (reentrancy
> guard, locality check, mount-prefix stripping). Do not reintroduce it.

### `create_app()` Per-App State Isolation (DEMOMA-01-004)

Each `create_app()` call MUST produce a fully isolated app:

1. `app.state.dispatcher` — fresh per call, never a module-level global.
2. `app.state.emitter` — an `HttpDeliveryAdapter` instance per lifespan;
   never shared across apps.
3. `DataLayer` — via `app.dependency_overrides`, never a shared module-level
   dict.

Module-level globals are silently overwritten by the last lifespan to run.
Root cause of bug #534 (PR #540).

Two `create_app()` calls in the same process MUST NOT share a `DataLayer` —
sharing bypasses outbox→inbox delivery entirely (DEMOMA-01-005).
