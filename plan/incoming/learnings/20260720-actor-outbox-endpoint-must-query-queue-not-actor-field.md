---
title: Actor outbox endpoint must query DataLayer queue, not actor.outbox field
type: learning
timestamp: 2026-07-20T00:00:00Z
source: ISSUE-1515
---

## Observation

`GET /datalayer/Actors/{actor_id}/outbox/` used to call `dl.read(actor_id)`,
then `as_Actor.model_validate(actor_obj.model_dump(...))`, and then iterate
over `actor.outbox.items`.

After ADR-0034 / PR #1512, `dl.read()` returns a `CoreActor` whose `outbox`
field is a plain `str | None` URI — not an `as_OrderedCollection`.
`as_Actor._coerce_uri_to_collection` converts that URI to an
`as_OrderedCollection(id_=uri)` with an empty `items` list, so the endpoint
silently returned zero items regardless of the actor's actual outbox queue.

## Fix

Replace the actor-object coercion path with a direct DataLayer queue query:

```python
activity_ids = cast(CaseOutboxPersistence, datalayer).outbox_list_for_actor(actor_id)
outbox = as_OrderedCollection(id_=f"{actor_id}/outbox")
outbox.items = [rehydrate(aid, dl=datalayer) for aid in activity_ids]
```

The actor `read()` result is still used only for the 404 guard.

## Generalisation

Any endpoint that needs the *contents* of an actor's outbox queue must call
`outbox_list_for_actor(actor_id)` directly — not look at `actor.outbox.items`,
which is always empty after ADR-0034. The actor object's `outbox` field is now
only a URI pointer to the collection endpoint, not the collection itself.
