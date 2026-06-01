# AGENTS.md — vultron/adapters/

> For project-wide conventions see the root
> [AGENTS.md](../../AGENTS.md). This file covers rules specific to the
> adapters layer: FastAPI driving adapters, driven adapters (DataLayer
> implementations), and demo scripts.

---

## FastAPI Driving Adapter Conventions

- **202 immediately**: Inbox endpoints MUST return HTTP 202 within ~100 ms.
  Schedule actual work with `BackgroundTasks`. Do not block the response
  on message processing.
- **Layer boundary**: Routers in `vultron/adapters/driving/fastapi/routers/`
  MUST NOT import from `vultron/core/` directly except through the
  dispatcher port. No business logic in routers.
- **response\_model filtering**: FastAPI's `response_model=` strips fields
  not declared on the model. Use a wide-enough model or `response_model=None`
  when returning subtype objects.
  See [notes/codebase-structure.md](../../notes/codebase-structure.md)
  § FastAPI response\_model Filtering.

---

## Key Files Map — adapters layer

- **Inbox**: `vultron/adapters/driving/fastapi/routers/actors.py`
- **Triggers**: `vultron/adapters/driving/fastapi/routers/trigger_*.py`
- **Errors**: `vultron/errors.py`,
  `vultron/adapters/driving/fastapi/errors.py`
- **TinyDB adapter**: `vultron/adapters/driven/datalayer_tinydb.py`
- **ASGI Emitter**: `vultron/adapters/driven/asgi_emitter.py` — routes
  in-process deliveries via ASGI; see
  [notes/asgi-emitter.md](../../notes/asgi-emitter.md)

---

## Demo Script Conventions

Use `demo_step` / `demo_check` context managers (`vultron/demo/utils.py`) to
wrap every workflow step and verification block. See
[notes/codebase-structure.md](../../notes/codebase-structure.md) §
"Demo Script Lifecycle Logging" for the full pattern.

Scenario demos MUST puppeteer via trigger endpoints, not spoof inboxes
directly. See
[notes/event-driven-control-flow.md](../../notes/event-driven-control-flow.md).

---

## Common Pitfalls — adapters layer

See [notes/architecture-ports-and-adapters.md](../../notes/architecture-ports-and-adapters.md)
for:

- Avoid `BaseModel` in Port/Adapter Type Hints
- Co-located Actor IDs Must Be HTTP-Routable; Wire Up `ASGIEmitter` at
  Startup
- ASGIEmitter Path Construction: Use Scheme+Netloc Only as `httpx` Base URL
- `create_app()` MUST NOT Mutate Module-Level Singletons
- **DataLayer Scope Boundaries: Shared vs. Actor-Scoped** — queue methods
  (`inbox_list`, `inbox_pop`, `outbox_list`, `outbox_pop`) MUST use an
  actor-scoped DataLayer, not the shared one. An unscoped DL silently
  operates on the wrong (empty) queue.
- **DataLayer Identity Contract: Canonical URI Must Match** — the actor_id
  used to construct an actor-scoped DataLayer for queue reads MUST be the
  actor's canonical URI (`actor.id_`), and MUST exactly match the string
  passed to `record_outbox_item` by the use case. Use
  `get_canonical_actor_dl()` from `deps.py`; do NOT pass the raw URL path
  segment. Violating this causes outbound activities to be silently dropped
  (BUG-2026040901).

See [notes/codebase-structure.md](../../notes/codebase-structure.md) for:

- Circular Imports
- FastAPI response\_model Filtering
- Health Check Readiness Gap
- Docker Health Check Coordination
- Actor IDs Must Always Be Full URIs
- Actor ID Normalization in Trigger Paths: Resolve Path Params Before Outbox
- Black Can Invalidate Inline pyright Suppressions on Wrapped Fields

### URL-Keyed IDs in FastAPI Path Segments

When an endpoint accepts an object ID that may be a full HTTP URL (e.g.,
`http://host:port/api/v2/actors/case-actor-{uuid}/participant`), use the
Starlette `{param:path}` converter — **not** `{param}`:

```python
# ✅ Accepts keys with embedded slashes (e.g., full HTTP URL IDs)
@router.get("/{key:path}")
def get_object_by_key(key: str, ...): ...
```

Starlette decodes `%2F` → `/` before route matching, so percent-encoding is
not a client-side fix. Register `{param:path}` catch-all routes **last** so
that specific literal routes (`/Offers/`, `/Actors/`) are matched first.

See
[notes/codebase-structure.md](../../notes/codebase-structure.md)
§ Starlette Path-Type Parameters for URL-Keyed Endpoints.
