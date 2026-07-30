---
source: ISSUE-1823
timestamp: '2026-07-30T13:41:56.848501+00:00'
title: 'fix(demo-ci): raise DeliveryError on exhausted retries so outbox_handler requeues
  lost activities'
type: implementation
---

Fixes #1823. Root cause: DemoHttpDeliveryAdapter._deliver_with_retry silently
logged and returned on final retry exhaustion. outbox_handler never received an
exception, never requeued the activity, and OutboxMonitor could not recover it.
Any activity that exhausted all 4 delivery attempts (3 retries × 5 s timeout)
was permanently lost, causing downstream demo polling (find_case_invite_for_actor,
verify_replica_state, wait_for_note_in_case) to time out.

Fix: _deliver_with_retry now raises DeliveryError on final failure. emit()
catches per-recipient to preserve isolation, collects failures, and re-raises
after all recipients are attempted so outbox_handler requeues the item for
OutboxMonitor retry (OX-05-002).

Added test_exhaust_retries_raises and
test_failed_recipient_raises_after_all_recipients_attempted; updated 4 existing
tests that previously asserted no-raise on exhaustion.

PR: <https://github.com/CERTCC/Vultron/pull/1830>
