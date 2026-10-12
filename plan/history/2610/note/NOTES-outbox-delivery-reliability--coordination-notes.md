---
source: NOTES-outbox-delivery-reliability--coordination-notes
timestamp: '2026-10-12T19:36:17.885399+00:00'
title: 'Outbox delivery reliability: coordination notes'
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered — #2202 closed; bounded inbox retry landed in #4168 (IE-06-004); #1880 closed; OX-12-001 HTTP-only delivery is settled (ADR-0042)
**Superseded by:** `vultron/adapters/driving/fastapi/inbox_handler.py` (bounded inbox retry), `AppConfig.max_inbox_retry_attempts`, ADR-0066

---

## Coordination Notes

- **#2202 AC-7**: that issue consolidates demo-side timeout constants. Once
  `HttpDeliveryAdapter.timeout` is configurable (Task C), #2202 can set it from
  a single config source rather than the hardcoded 5 s.
- **#1880 / #4168 (IE-06-004)**: the "analogous inbound terminal-state question"
  ADR-0066 deferred has landed for bounded inbox retry in #4168.
  The mechanism is now shared: a single `QueueAttemptEntry` SQLModel table
  (composite PK: `queue` + `activity_id`) backs both inbox and outbox attempt
  counters.
  `RetryStore` (extending `OutboxRetryStore`) is the unified adapter protocol.
  `InboxDeadLetterEntry(CoreRecord)` mirrors `OutboxDeadLetterEntry`.
  `AppConfig.max_inbox_retry_attempts` (default 12) makes the inbox budget
  configurable via `VULTRON_MAX_INBOX_RETRY_ATTEMPTS`.
  Protocol-level NACK on exhaustion is still deferred to #1880.
- **OX-12-001**: HTTP-only delivery (ADR-0042) is not in question. All changes here
  are about the reliability envelope, not the delivery mechanism.
