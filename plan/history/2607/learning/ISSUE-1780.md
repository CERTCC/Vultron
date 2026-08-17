---
title: Dual emitter resolution paths in outbox BackgroundTasks
type: learning
timestamp: 2026-07-31T00:00:00Z
source: ISSUE-1780
signal: design-question
---

When retiring ASGIEmitter (ISSUE-1780), a non-obvious architectural invariant surfaced: outbox delivery resolves the `ActivityEmitter` via two distinct paths, and both must be patched in tests:

1. **Trigger-route BackgroundTasks** — `POST /actors/{id}/outbox/` schedules `outbox_handler(actor_id, dl)` with no emitter argument. The handler calls `get_default_emitter()` → patched via `configure_default_emitter(router)`.

2. **Inbox-route BackgroundTasks** — `POST /actors/{id}/inbox/` schedules `outbox_handler(actor_id, dl, emitter=getattr(request.app.state, "emitter", None))`. If `app.state.emitter` is set, it bypasses `get_default_emitter()` entirely.

The `client` fixture must patch **both** to intercept all deliveries:

```python
configure_default_emitter(router)   # covers trigger-route tasks
api_app.state.emitter = router       # covers inbox-route tasks
```

Isolated apps (`configure_globals=False`) avoid the second path by never setting `app.state.emitter`, falling back to `get_default_emitter()` for both paths. This is why `_make_lifespan` conditionalises the emitter creation on `configure_globals`.

Future developers adding new endpoints that schedule `outbox_handler` must explicitly decide which resolution path they use and ensure test fixtures cover it.

**Promoted**: 2026-08-17 — captured in AGENTS.md pitfall: outbox BackgroundTasks emitter has two resolution paths.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>0>0>0>0>0>0>0>0>0>.
