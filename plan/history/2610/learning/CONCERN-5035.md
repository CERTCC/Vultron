---
source: CONCERN-5035
timestamp: '2026-10-21T17:33:01.413480+00:00'
title: The inbox queue replay loses an item when the process stops during an attempt
type: learning
---

## Problem

The inbox queue replay (`drain_inbox_queue` in `vultron/adapters/driving/fastapi/inbox_queue_drain.py`) pops an item's id from the inbox queue, then rebuilds the item with `InlineObjectStaging.rehydrate_deferred`, which deletes the held `DeferredInboxActivity` record. Both writes happen before the attempt runs. So if the process stops during an attempt, the item is lost: its id is no longer queued and its record is gone. A stop between `hold_again` and `inbox_append` in a failed attempt leaves a held record that no queue reaches.

The receiver keeps no other copy of a received activity (DL-06-006), and the sender gets no fault, so nothing recovers the item.

## Why it matters

The persisted attempt count (IE-06-004) assumes the item survives a restart. Today only the count does.

## Context

This is pre-existing: main had the same pop-then-rebuild order in `run_inbox_pipeline`, and so did the removed `inbox_handler()` worker. The pre-push review of PR #5034 (#5021) found it. It was left out of that PR because the user asked for no recovery machinery beyond IE-06-004 in this prototype.

## Possible direction

Pop the id only after the attempt is settled, or write hold, count and append in one transaction. Add a test that interrupts an attempt.

Governing specs: IE-06-004, DL-06-006

Where: vultron/adapters/driving/fastapi/inbox_queue_drain.py

**Resolved**: 2026-10-21 — implementation tracked in #5051.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5050>.
Spec: `specs/inbox-endpoint.yaml` (IE-06-005, IE-06-006).
Notes: `notes/inbox-pipeline.md`.

Decisions: each replay attempt commits as one DataLayer transaction (exactly-once, per
ADR-0146) rather than settle-after-attempt (at-least-once); the plan also adds a
startup replay of queued inbox items, since a surviving item otherwise waits for the
next delivery to the same actor.
