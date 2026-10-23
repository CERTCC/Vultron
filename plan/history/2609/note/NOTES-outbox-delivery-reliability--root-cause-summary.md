---
source: NOTES-outbox-delivery-reliability--root-cause-summary
timestamp: '2026-09-17T17:32:38.786458+00:00'
title: Root Cause Summary (CONCERN-2302 §7)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered/resolved
**Superseded by:** outbox_handler.py + http_delivery.py; CONCERN-2302 closed

---

## Root Cause Summary (CONCERN-2302 §7 resolution)

`outbox_handler.py`'s `err_count > 3: break` does **not** silently drop outbox
entries — `outbox_pop()` removes the item and `outbox_append()` re-queues it before
the break. The liveness failure is: when the first *N* items in the queue all fail
in the same drain pass, `err_count` hits 4 before later (non-failing) activities are
reached. Critical ledger-entry deliveries for healthy recipients are delayed past the
scenario timeout. Severity: **liveness/performance failure**, not data-integrity loss.

---
