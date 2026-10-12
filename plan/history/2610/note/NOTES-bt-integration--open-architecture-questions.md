---
source: NOTES-bt-integration--open-architecture-questions
timestamp: '2026-10-12T19:35:41.056215+00:00'
title: Open Architecture Questions
type: note
---

**Archived:** 2026-10-12
**Reason:** answered or no longer open: per-actor sequential processing under the BT RLock settled multi-actor synchronization; outbox delivery is asynchronous via OutboxMonitor; human-in-the-loop decisions are call-out points and protocol asks
**Superseded by:** notes/bt-integration.md § Concurrency Model; ADR-0112; notes/outbox-delivery-reliability.md; notes/call-out-configuration.md; ADR-0080

---

## Open Architecture Questions

**Multi-actor state synchronization**: Each actor's BT loads only that
actor's DataLayer state. Cross-actor coordination happens via message
exchange. Whether to add optimistic locking for multi-actor scenarios should
be decided based on observed issues during testing.

**Message emission and outbox processing**: BT nodes generate activities and
write to actor outbox via DataLayer. Whether outbox delivery should be
triggered synchronously after BT execution or asynchronously remains to be
decided.

**Human-in-the-loop decision handling**: Report validation, embargo
acceptance, and similar steps require human judgment. The prototype uses
configurable default policies (always-accept stubs with audit logging). Async
workflow support with pause/resume is a future consideration.
