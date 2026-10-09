---
source: CONCERN-3638
timestamp: '2026-09-29T13:58:35.656307+00:00'
title: Inbox route's duplicate-delivery guard is a silent no-op for string inboxes
type: learning
---

## Concern

The inbox route's duplicate-delivery guard doesn't work, and it isn't clear whether that is deliberate or a regression.

`POST /actors/{id}/inbox/` (`vultron/adapters/driving/fastapi/routers/actors/_routes.py:557-567`) runs two checks on every inbound activity:

- `_activity_already_received(actor, activity.id_)` returns early if the activity was already received.
- `_record_inbox_receipt(dl, actor, activity.id_, ...)` records the receipt "so the dedup guard on the next delivery of the same activity_id sees the updated actor inbox record."

Both helpers (`_inbox.py:181`, `_inbox.py:351`) read or append `actor.inbox.items`. The actor comes from the DataLayer as a `CoreActor`, whose `inbox` is a URL **string** (ADR-0099 / #3540, never empty since #3614). As a result:

- `_activity_already_received` always returns `False`.
- `_record_inbox_receipt` does nothing.
- A redelivered activity (peer retry, duplicate POST) goes through the full inbound pipeline again.

## Why it's unclear

- **Evidence it was known:** `vultron/demo/helpers/verification.py:437` says the `inbox.items` path "is not used because `_record_inbox_receipt` is a no-op when `inbox` is a string URI". It switched to a DataLayer lookup instead (#2356). So someone noticed, worked around it in the demo helper, and left the route alone.
- **Evidence it was lost:** the route comment still describes an active guard, and nothing replaced it at the route level. Many received use cases are individually idempotent (`_idempotent_create`, "skipping (idempotent)" in `received/status.py`, `embargo.py`, `note.py`, `case/lifecycle.py`). That may be the intended replacement, or it may only cover part of it; it has not been checked.
- **Tests hide it:** `test/adapters/driving/fastapi/routers/actors/test_inbox.py:110-130, 311-327` and `test_inbox_route_log_levels.py:96` exercise the helpers with wire `as_Organization` actors or stubs that have `inbox.items`, a shape the route never receives. The one `CoreActor` case asserts the no-op as expected behaviour.

## Direction / evidence needed

1. Decide whether route-level dedup is a requirement. Look for IE/IDEM specs covering duplicate delivery; ActivityPub receivers are expected to tolerate redelivery.
2. If it is a requirement, back it with something that exists, e.g. "activity id already stored in the recipient's DataLayer", which is the check `verify_activity_in_inbox` already uses. Then add a route-level test that POSTs the same activity twice to a real `CoreActor`.
3. If per-handler idempotency is the intended design, delete both helpers, the route call sites and the misleading comment, and retarget the tests.

Surfaced while tightening `CoreActor.inbox` to a never-empty `str` in #3614.

**Resolved**: 2026-09-29 — implementation tracked in #3867. The route-level cleanup
(deleting the no-op guard and its tests) was delivered independently by #3844 /
PR #3854 during the planning of #3141; the inbox-endpoint spec (IE-10-001) places
redelivery detection at ingress storage, and this planning adds the missing proof
that a redelivered activity causes no second side effect once the stored copy
reaches the handler.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3866>.
Spec: `specs/idempotency.yaml`.
