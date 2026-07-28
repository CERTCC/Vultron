---
source: ISSUE-1515
timestamp: '2026-07-20T13:41:03.314294+00:00'
title: fix actor outbox endpoint empty items after ADR-0034
type: implementation
---

Issue #1515: GET /datalayer/Actors/{actor_id}/outbox/ always returned empty items
after PR #1512 (ADR-0034) changed dl.read() to return CoreActor objects.
CoreActor.outbox is a plain str URI; coercing it to as_Actor via model_validate
produced an empty as_OrderedCollection with no items. Root cause: endpoint read
from the actor object field instead of the DataLayer queue. Fix: replaced
actor-coercion path in get_actor_outbox with
CaseOutboxPersistence.outbox_list_for_actor(actor_id). Added three regression
tests. PR: <https://github.com/CERTCC/Vultron/pull/1522>
