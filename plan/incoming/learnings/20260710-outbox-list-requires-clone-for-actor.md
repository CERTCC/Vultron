---
title: "outbox_list() uses dl._actor_id; tests must use clone_for_actor or outbox_list_for_actor"
type: learning
timestamp: 2026-07-10T14:00:00Z
source: ISSUE-1298
---

`SqliteDataLayer.outbox_list()` reads the outbox for `dl._actor_id`, which is
empty (`""`) on a freshly constructed `SqliteDataLayer("sqlite:///:memory:")`.
BT nodes call `record_outbox_item(actor_id, activity_id)` which writes to the
named actor's queue — these two paths don't share the same key unless the DL
was constructed via `clone_for_actor(actor_id)`.

**In tests that verify outbox contents after use case execution:**

- Use `dl.outbox_list_for_actor(local_actor_id)` to read by explicit actor ID.
- Or use `dl.clone_for_actor(actor_id).outbox_list()` (the pattern used in BT tests).
- `dl.outbox_list()` always returns `[]` unless `dl._actor_id` is set.
