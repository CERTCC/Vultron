---
source: CONCERN-650
timestamp: '2026-06-03T19:59:13.695772+00:00'
title: Remote HTTP delivery and shared-inbox are architectural stubs with no implementation
type: learning
---

## Summary

`vultron/adapters/driven/http_delivery.py` and
`vultron/adapters/driving/shared_inbox.py` are placeholder files with no
working implementation. Current remote delivery uses plain unauthenticated
HTTP POST via `DeliveryQueueAdapter`. Message signing and shared-inbox
fan-out remain unimplemented stubs.

## Category

- Top risk
- Technical debt

## Severity

medium

## Evidence

- `vultron/adapters/driven/http_delivery.py` — stub, no implementation
- `vultron/adapters/driving/shared_inbox.py` — stub, no implementation
- `vultron/adapters/driven/delivery_queue.py` — plain HTTP POST delivery path

## Impact if Ignored

Multi-party interoperability and security posture are limited until signed
delivery paths exist. Callers may assume these modules are functional,
leading to silent no-ops in production-like deployments.

## Resolution

Root cause: signed remote delivery and shared-inbox fan-out are intentionally
deferred prototype shortcuts, but were not visibly marked at the code or spec
level — creating a silent-failure risk.

Fix: spec entries added (OX-10-\* for signed delivery, OX-11-\* for
shared-inbox fan-out) requiring `NotImplementedError` in stubs until
implemented. `notes/architecture-adapters.md` updated with spec references.
`AGENTS.md` pitfall added: stub adapter files must raise `NotImplementedError`,
not silently no-op.

**Resolved**: 2026-06-03 — implementation tracked in #717 (signed HTTP
delivery) and #718 (shared-inbox fan-out).
Docs PR: <https://github.com/CERTCC/Vultron/pull/719>.
