---
source: NOTES-datalayer-design--retired-outbox-list-clone-for-actor
timestamp: '2026-09-01T22:00:58.528398+00:00'
title: 'Retired: outbox_list() requires clone_for_actor in tests'
type: note
---

Archived from `notes/datalayer-design.md` § "RETIRED: `outbox_list()` Requires
`clone_for_actor` in Tests" (ISSUE-1298, 2026-07-10; retired by ADR-0073 /
ISSUE-2238, 2026-08-20).

Removed from `notes/` because the pitfall no longer exists and notes/ states
current understanding only. Original text:

> This pitfall no longer exists. It described a writer and a reader disagreeing
> about which `actor_id` string keyed a queue row — `record_outbox_item(actor_id,
> …)` wrote under a named actor while `outbox_list()` read under `dl._actor_id`,
> which was `""` on a freshly constructed DataLayer.
>
> Neither half survives. A DataLayer cannot be constructed without an actor
> (DL-07-002), so there is no `""` scope to fall into; and queue rows carry no
> `actor_id` column at all (DL-07-001) — the queue lives in its owner's store, so
> `record_outbox_item` and `outbox_list_for_actor` collapsed into `outbox_append`
> and `outbox_list`.

The live lesson it was kept for — a writer and a reader disagreeing about which
store they address — is now carried by § "One Actor Id Is One Database" and by
BT-05-005 (a BT's store follows its executing actor).
