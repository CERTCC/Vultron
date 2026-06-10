# Driven Adapters — Design Rules

## ASGIEmitter Design Rules

`ASGIEmitter` (`vultron/adapters/driven/asgi_emitter.py`) is the
production `ActivityEmitter` implementation for the FastAPI server. It
delivers activities to co-located actors in-process via the ASGI
interface and falls back to `DemoHttpDeliveryAdapter` (HTTP POST) for
remote recipients.

References: `specs/multi-actor-demo.yaml` DEMOMA-01-004,
DEMOMA-01-005; `vultron/core/ports/AGENTS.md` § Dispatch vs Emit
Terminology.

### Path Construction Rule

#### Problem: double path prefix

When `base_url` includes a path component (for example,
`http://host/api/v2`), passing the full `base_url` to
`httpx.AsyncClient` causes a double-prefix bug:

```text
base_url = "http://host/api/v2"
inbox_path = "/api/v2/actors/abc/inbox/"

# httpx appends inbox_path to the base path -> "/api/v2/api/v2/actors/abc/inbox/"
# Result: HTTP 404 on every local delivery
```

This was the root cause of bugs #557 and #558 (PR #559).

#### Fix: scheme+netloc only as httpx base URL

`ASGIEmitter._try_deliver_local()` MUST construct the
`httpx.AsyncClient.base_url` using **scheme and netloc only** — never
the full configured `base_url`:

```python
parsed_base = urlparse(self._base_url)
asgi_base_url = f"{parsed_base.scheme}://{parsed_base.netloc}"
# e.g., "http://vendor:7999" — no path component
```

The inbox path is then passed as-is to `httpx.AsyncClient.post()`, so
the final URL is constructed correctly:

```text
asgi_base_url = "http://host"
inbox_path    = "/api/v2/actors/abc/inbox/"
-> POST http://host/api/v2/actors/abc/inbox/  ✓
```

### `mount_prefix` Stripping Rule

`ASGIEmitter` accepts an optional `mount_prefix` parameter (for example,
`"/api/v2"`) that records the URL path prefix at which the actor sub-app
is mounted within the outer application. When delivering locally, the
emitter strips this prefix from the inbox path before routing into the
sub-app, because the sub-app itself does not know it is mounted at a
prefix:

```python
# inbox_path as extracted from the recipient ID
inbox_path = "/api/v2/actors/abc/inbox/"

# Strip mount_prefix -> path relative to the sub-app
inbox_path = "/actors/abc/inbox/"
```

`mount_prefix` MUST be the exact path prefix at which the target sub-app
is mounted (no trailing slash). If `mount_prefix` is empty, no stripping
occurs and the full path is forwarded as-is.

Wiring:

```python
configure_default_emitter(
    ASGIEmitter(app=router_app, mount_prefix="/api/v2"),
)
```

### Locality Check: `_is_local_recipient`

`ASGIEmitter._is_local_recipient()` decides whether a recipient should be
delivered via ASGI or HTTP by comparing the recipient URL's scheme and
netloc against the configured `base_url`. Two actors are co-local if and
only if they share the same scheme+netloc.

In a Docker Compose deployment, all actor IDs on the same container MUST
use that container's hostname (for example, `http://vendor:7999/...`),
not `http://localhost:...`. Localhost-based IDs cause every container to
treat all actors as local, routing inter-container deliveries into the
wrong process.

### `create_app()` Per-App State Isolation

#### Contract (DEMOMA-01-004)

Each call to `create_app()` MUST produce a fully isolated FastAPI
application. Specifically:

1. The dispatcher (`app.state.dispatcher`) MUST be created fresh and
   stored on `app.state`, not on a module-level global like
   `_DISPATCHER`.
2. The emitter (set via `configure_default_emitter()`) MUST be stored on
   `app.state`, not on a module-level global like `_default_emitter`.
3. The `DataLayer` MUST be registered in `app.dependency_overrides` (or
   created fresh via `_auto_inject_isolated_datalayer()`), never shared
   via a module-level `_shared_instance` or `_actor_instances` dict.

When multiple co-located actors are hosted in the same Python process,
each actor's lifespan runs `create_app()`. If any of those three
resources lives in a module-level global, the last lifespan to run
overwrites it — the first actor's dispatcher and DataLayer are silently
replaced. The first actor then uses the second actor's storage,
bypassing the outbox -> inbox delivery path entirely.

This was the root cause of bug #534 (PR #540).

#### Correct wiring pattern

```python
# Each create_app() call produces an independent FastAPI instance with its own
# lifespan. The lifespan automatically:
#   - Creates a fresh per-app dispatcher stored on app.state.dispatcher.
#   - Injects a fresh SqliteDataLayer via app.dependency_overrides[get_shared_dl]
#     when no override has been registered.
app = create_app(docs_url=None, openapi_url=None)
# Optionally register a specific DataLayer before the lifespan starts:
# app.dependency_overrides[get_shared_dl] = lambda: my_dl
with TestClient(app) as client:
    ...
```

#### Co-located actor isolation (DEMOMA-01-005)

Two `create_app()` calls in the same process MUST NOT share a `DataLayer`
instance. Each app must have its own isolated in-memory or file-backed
database so that objects created by Actor A are only visible to Actor B
after outbox delivery occurs. Sharing a `DataLayer` bypasses delivery
entirely and makes integration tests unreliable.

### Reentrancy Guard

`ASGIEmitter` uses a `contextvars.ContextVar[int]`
(`_asgi_delivery_depth`) to prevent recursive ASGI delivery within the
same asyncio task. If a delivery chain triggers another delivery on the
same task, the inner delivery falls through to the HTTP fallback adapter
instead of re-entering the ASGI app.

This guard is per-task (each new HTTP request handled by uvicorn starts
at depth 0), so cross-request delivery chains in production are
unaffected.
