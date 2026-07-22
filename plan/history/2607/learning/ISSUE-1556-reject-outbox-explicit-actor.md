---
title: "Sync reject outbox must enqueue against explicit actor_id, not DL scope"
type: learning
timestamp: "2026-07-21T00:00:00+00:00"
source: ISSUE-1556
---

`SyncActivityAdapter.send_reject_log_entry` used `self._dl.outbox_append(id)`,
which enqueues against the DataLayer's *own* `_actor_id` scope and wakes
`_enqueue_callback(dl._actor_id)`. Its sibling `send_announce_log_entry` used
`add_activity_to_outbox(actor_id, id, dl)` → `record_outbox_item(actor_id, id)`,
which enqueues against the *explicit* recipient actor regardless of the DL's
scope. When the reject is emitted from a shared or differently-scoped DataLayer,
`outbox_append` can queue it to the wrong (or empty-scope) outbox — a plausible
contributor to "the CaseActor never processes the participant's Reject" at
closure fan-out.

**Rule:** any adapter that emits an activity *on behalf of a specific actor*
must enqueue with `record_outbox_item(actor_id, …)` / `add_activity_to_outbox`,
never the scope-dependent `outbox_append`. `outbox_append` is only correct when
the DL is already scoped to the emitting actor and that scope is guaranteed.

Test impact: tests asserting the reject lands in `dl.outbox_list()` (the
DL-scope queue) must switch to `dl.outbox_list_for_actor(receiving_actor_id)`
and set `receiving_actor_id` on the event (the inbox pipeline always does this
in production).

**Promoted**: 2026-07-22 — captured in `notes/sync-ledger-replication.md (already present)`.
Docs PR: TBD (fill in after PR is opened).
