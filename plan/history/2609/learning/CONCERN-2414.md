---
source: CONCERN-2414
timestamp: '2026-09-14T17:16:07.238005+00:00'
title: pytest coverage gaps leave multi-actor integration correctness CI-only
type: learning
---

Seven local pytest coverage gaps (identified in #1970) meant multi-actor protocol
correctness was only verifiable via Docker Compose CI (10–20 min round-trips). Six
of the seven gaps were addressed by #1976 (invariant ratchet in-memory fixtures,
milestone assertions in demo tests, use-case chain tests, PEC invite→accept BT
chain, outbox to-field assertions, participant-state predicates extracted to core).
The remaining gap — delivery failure → requeue path (#1877) — was tracked but
blocked pending a design decision.

**Resolved**: 2026-09-14 — design decision recorded in #1877 (inject DeliveryError
via _failing_hosts set on _TestClientRouter); implementation tracked in #1877.
