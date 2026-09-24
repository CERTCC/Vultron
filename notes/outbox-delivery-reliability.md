---
title: Outbox Delivery Reliability
status: active
description: >
  Implementation guidance for the outbox delivery reliability hardening tasks:
  per-activity abort scope, 4xx terminal classification, timeout/jitter/pool
  configuration, and per-activity attempt counter with dead-letter store.
related_specs:
  - specs/outbox.yaml
  - specs/sync-ledger-replication.yaml
related_issues:
  - https://github.com/CERTCC/Vultron/issues/2302
relevant_packages:
  - vultron/adapters/driven/http_delivery.py
  - vultron/adapters/driving/fastapi/outbox_handler.py
---

# Outbox Delivery Reliability

Implementation guidance for CONCERN-2302 remediation. See ADR-0066 for the
architectural rationale and option analysis.

---

## Coordination Notes

- **#2202 AC-7**: that issue consolidates demo-side timeout constants. Once
  `HttpDeliveryAdapter.timeout` is configurable (Task C), #2202 can set it from
  a single config source rather than the hardcoded 5 s.
- **#1880**: inbound unprocessable activities — the analogous inbound terminal-state
  question. ADR-0066 defers the protocol-level NACK to that issue; the dead-letter
  store model should be unified when #1880 is planned.
- **OX-12-001**: HTTP-only delivery (ADR-0042) is not in question. All changes here
  are about the reliability envelope, not the delivery mechanism.
