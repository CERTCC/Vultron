# Driven Adapters — Design Rules

## ASGIEmitter Design Rules

`ASGIEmitter` delivers to co-located actors via ASGI; falls back to
`DemoHttpDeliveryAdapter` (HTTP POST) for remote. See DEMOMA-01-004, DEMOMA-01-005.

### Path Construction Rule

`_try_deliver_local()` MUST use **scheme+netloc only** as the `httpx` base URL
— never the full `base_url`. A path component causes a double-prefix 404:

```python
parsed_base = urlparse(self._base_url)
asgi_base_url = f"{parsed_base.scheme}://{parsed_base.netloc}"
```

Root cause of bugs #557, #558 (PR #559).

### `mount_prefix` Stripping Rule

`mount_prefix` (e.g. `"/api/v2"`) is the path prefix at which the sub-app is
mounted. The emitter strips it before routing into the sub-app. No trailing
slash. Empty = no stripping.

```python
configure_default_emitter(ASGIEmitter(app=router_app, mount_prefix="/api/v2"))
```

### Locality Check

`_is_local_recipient()` compares scheme+netloc. In Docker Compose, actor IDs
MUST use the container hostname (`http://vendor:7999/...`), not `localhost`.

### `create_app()` Per-App State Isolation (DEMOMA-01-004)

Each `create_app()` call MUST produce a fully isolated app:

1. `app.state.dispatcher` — fresh per call, never a module-level global.
2. `app.state` emitter — never `_default_emitter` module-level global.
3. `DataLayer` — via `app.dependency_overrides`, never a shared module-level dict.

Module-level globals are silently overwritten by the last lifespan to run.
Root cause of bug #534 (PR #540).

Two `create_app()` calls in the same process MUST NOT share a `DataLayer` —
sharing bypasses outbox→inbox delivery entirely (DEMOMA-01-005).

### Reentrancy Guard

`_asgi_delivery_depth` (`contextvars.ContextVar[int]`) prevents recursive ASGI
delivery within the same asyncio task — inner delivery falls through to HTTP
fallback. Guard is per-task, so cross-request chains in production are unaffected.
