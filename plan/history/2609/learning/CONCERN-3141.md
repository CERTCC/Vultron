---
source: CONCERN-3141
timestamp: '2026-09-28T18:58:34.942705+00:00'
title: 'The inbox has no read surface: GET /actors/{id}/inbox stub and dead receipt
  helpers'
type: learning
---

## Summary

`GET /actors/{id}/inbox` is an explicit "(stub implementation)" that returns the transient inbox *processing queue*, which is drained during processing, so it reports an empty inbox even for activities the actor successfully received and processed.

## Surface symptom vs. underlying problem

- **Surface symptom:** After POSTing a `Create(VulnerabilityReport)` to an actor's inbox and receiving `202 Accepted`, a follow-up `GET /actors/{id}/inbox` returns an empty `OrderedCollection`.
- **Underlying problem:** The GET endpoint (`vultron/adapters/driving/fastapi/routers/actors/_routes.py:484-504`) returns `list(datalayer.inbox_list())` — the `"inbox"` *queue*. The inbox pipeline pops that queue as it processes each item (`inbox_handler.py`: `while queue_dl.inbox_list(): ... inbox_pop`), so once processing finishes the queue is empty. The actual receipt is recorded on a *different* structure: `_record_inbox_receipt` (`_inbox.py:346-356`) appends the activity id to `actor.inbox.items`, which the GET endpoint never reads. There is therefore no working way to confirm receipt through the ActivityStreams inbox endpoint.

## Evidence

- `_routes.py:484-504` — `get_actor_inbox` returns `datalayer.inbox_list()`; description says "(stub implementation)".
- `_inbox.py:356` — `inbox.items.append(activity_id)` (receipt recorded here).
- `inbox_handler.py:413` — `while queue_dl.inbox_list():` drains the queue during processing.
- Observed live: create actor → POST inbox → 202 → `GET .../inbox` returns `{"items": []}`; the report is retrievable only via `GET /actors/{id}/datalayer/Reports/`.

## Impact if ignored

Clients of the ActivityPub-shaped API cannot see what an actor has received via the inbox endpoint — a surprising, misleading gap. The "Submit a report" tutorial (#603) had to verify receipt via the datalayer `Reports/` endpoint instead of the inbox.

## Suggested action

Implement `GET /actors/{id}/inbox` to return the actor's received-items collection (`actor.inbox.items`, resolved to the stored activities) rather than the drained processing queue, and drop the "(stub implementation)" note once real. Check for overlap with #2886 (dereferenceable collections).

Deferred from PR: <https://github.com/CERTCC/Vultron/pull/3140>

**Resolved**: 2026-09-28 — recharacterized during planning; implementation tracked in #3844.

The concern's premise did not hold: `_record_inbox_receipt` is a no-op in production because `CoreActor.inbox` is a URI string (ARCH-12-006), so no receipt is recorded on `actor.inbox.items` and there is nothing for the GET to read. No caller reads the inbox GET, and ActivityPub gives inbox reads to the actor's owner only, authenticated — a surface Vultron does not have. Operator visibility already goes through the datalayer router; a sender learns disposition from reply activities in its own inbox. The plan removes the stub route (honouring IE-02-003's 405), deletes the dead receipt and duplicate-detection helpers (ingress storage already detects redelivery), and documents the reasoning.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3843>.
Spec: `specs/inbox-endpoint.yaml` (IE-02-003, IE-02-004, IE-10-001).
Notes: `vultron/adapters/AGENTS.md` § "The Inbox Has No Read Surface".
