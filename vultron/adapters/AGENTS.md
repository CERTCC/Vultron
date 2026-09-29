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
- **AS2 response pattern** (HTTP-09-002): Endpoints returning AS2 objects
  MUST use `AS2JSONResponse` from
  `vultron.adapters.driving.fastapi.responses`. Do NOT return a raw dict
  from `model_dump()` or the wire model object directly. Use `response_model=`
  on the decorator for OpenAPI schema only; `AS2JSONResponse` handles
  serialization and sets `Content-Type: application/activity+json`.

  ```python
  # Correct pattern
  @router.get("/cases/{id}", response_model=as_VulnerabilityCase)
  def get_case(id: str):
      ...
      return AS2JSONResponse(wire_case)  # handles model_dump(by_alias=True)
  ```

- **response\_model filtering**: FastAPI's `response_model=` strips fields
  not declared on the model when the route returns a non-Response value. The
  `AS2JSONResponse` pattern above bypasses this filtering entirely (FastAPI
  docs: returning a `Response` subclass skips response_model filtering).
  See [notes/codebase-structure-fastapi-patterns.md](../../notes/codebase-structure-fastapi-patterns.md)
  § FastAPI response\_model Filtering.

---

## Key Files Map — adapters layer

- **Inbox**: `vultron/adapters/driving/fastapi/routers/actors.py`
- **Triggers**: `vultron/adapters/driving/fastapi/routers/trigger_*.py`
- **Errors**: `vultron/errors.py`,
  `vultron/adapters/driving/fastapi/errors.py`
- **TinyDB adapter**: `vultron/adapters/driven/datalayer_tinydb.py`
- **HTTP Delivery Adapter**: `vultron/adapters/driven/http_delivery.py` —
  sole inter-actor delivery adapter (ADR-0042); see
  [vultron/adapters/driven/AGENTS.md](../../vultron/adapters/driven/AGENTS.md)

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

See [notes/architecture-adapters.md](../../notes/architecture-adapters.md)
for:

- Avoid `BaseModel` in Port/Adapter Type Hints
- `create_app()` MUST NOT Mutate Module-Level Singletons
- **DataLayer Scope Boundaries** — queue methods (`inbox_list`, `inbox_pop`,
  `inbox_append`, `outbox_list`, `outbox_pop`, `outbox_append`) take no
  `actor_id`: they act on the store's own actor. Under ADR-0073 there is no
  unscoped store to get this wrong with — `actor_id` is required at
  construction.
- **DataLayer Identity Contract: Canonical URI Must Match** — the actor_id
  used to construct a DataLayer for queue reads MUST be the actor's canonical
  URI (`actor.id_`), and MUST exactly match the one the writing store was
  built with. Use `get_canonical_actor_dl()` from `deps.py`; do NOT pass the
  raw URL path segment. Violating this reads a *different actor's* store, so
  outbound activities are silently dropped (BUG-2026040901).

See [notes/codebase-structure-fastapi-patterns.md](../../notes/codebase-structure-fastapi-patterns.md) for:

- Circular Imports
- FastAPI response\_model Filtering
- Health Check Readiness Gap
- Docker Health Check Coordination
- Black Can Invalidate Inline pyright Suppressions on Wrapped Fields

See [notes/codebase-structure.md](../../notes/codebase-structure.md) for:

- Actor IDs Must Always Be Full URIs
- Actor ID Normalization in Trigger Paths: Resolve Path Params Before Outbox

### Actor Outbox Endpoint Must Query the DataLayer Queue, Not `actor.outbox.items`

After ADR-0034, `dl.read(actor_id)` returns a `CoreActor` whose `outbox` field
is a plain `str | None` URI. `as_Actor._coerce_uri_to_collection` converts that
URI to an `as_OrderedCollection(id_=uri)` with an **empty** `items` list, so
iterating `actor.outbox.items` silently returns zero results regardless of the
actor's actual queue.

**Fix:** query the DataLayer queue directly:

```python
# `datalayer` here is *this* actor's own store (ADR-0073).
activity_ids = cast(CaseOutboxPersistence, datalayer).outbox_list()
outbox = as_OrderedCollection(id_=f"{actor_id}/outbox")
outbox.items = [rehydrate(aid, dl=datalayer) for aid in activity_ids]
```

The `dl.read(actor_id)` result is still useful for the 404 guard only. Any
endpoint that needs the *contents* of an actor's outbox queue MUST call
`outbox_list()` on that actor's own store — the `outbox` field on the actor
object is now only a URI pointer to the collection endpoint.

<!-- Source: ISSUE-1515 (ADR-0034) -->

---

### The Inbox Has No Read Surface; `inbox_list()` Is a Processing Queue, Not a Mailbox

The inbox path accepts POST only and answers every other method with 405
(IE-02-003, IE-02-004). Do not add a GET that renders "what this actor
received", and do not add receipt bookkeeping to the actor record to feed one:

- **`inbox_list()` is not a record of receipt.** The POST route hands the
  activity straight to `run_inbox_pipeline`; the DataLayer `inbox` queue holds
  only deferred or re-queued deliveries — activities replayed by
  `inbox_pending_queue.py` after a case bootstrap, or retried after a failed
  attempt — and the pipeline drains it as it processes them. A read over it
  reports an empty inbox after every successful delivery — the stub #3141
  reported and #3844 removed.
- **Removing the GET does not produce the 405.** `actors_get` is declared as
  `@router.get("/{actor_id:path}")`, so an unrouted GET on `/inbox` or
  `/inbox/` falls into the profile route and answers 404. The inbox path needs
  an explicit method refusal declared ahead of that catch-all.
- **`CoreActor.inbox` is a URI string** (ARCH-12-006), so any helper that
  reaches for `actor.inbox.items` is a no-op in production. The route-level
  receipt-recording and duplicate-guard helpers deleted in #3844 passed their
  tests only because those tests supplied an inbox with an `.items` list — a
  wire `as_Organization` in one file, a hand-rolled stub actor in another.
  A test of an actor-record helper must build a `CoreActor`.
- **The activity itself is already stored.** Ingress writes the received
  activity into the actor's store under its activity type; ingress storage is
  also where redelivery is detected (IE-10-001).
- **Who may look, and where.** Reading an actor's received mail is an operator
  concern, served by the datalayer router over that actor's own store
  (`/actors/{id}/datalayer/...`). A sender learns what became of what it posted
  from the reply activities delivered to *its* inbox — never by reading the
  recipient's. Trigger-side outcome observability is a separate question
  (#2369, #2886).

<!-- Source: CONCERN-3141 -->

---

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
§ "Starlette Path-Type Parameters for URL-Keyed Endpoints".
