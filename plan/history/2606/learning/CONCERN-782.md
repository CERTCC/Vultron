---
source: CONCERN-782
timestamp: '2026-06-08T20:25:22.624469+00:00'
title: Silent broadcast failure allows undetected peer state divergence
type: learning
---

## Summary

`BroadcastStatusToPeersNode` and similar broadcast nodes treat delivery failures as non-fatal: the BT node always returns `SUCCESS` regardless of whether peers actually received the update. Because there is no retry, dead-letter queue, or visibility mechanism, a failed broadcast leaves peers in a silently diverged state with no observable signal. The same "non-fatal" pattern appears in at least two places, suggesting broadcast logic is not yet centralized.

## Category

- [x] Top risk
- [ ] Technical debt
- [ ] Security
- [ ] Performance / scaling
- [ ] Fragile / high-churn area
- [ ] Other

## Severity

high

## Evidence

- `vultron/core/behaviors/status/nodes.py` — line 630: `BroadcastStatusToPeersNode` docstring "Always returns SUCCESS (failure to broadcast is not fatal)"; `py_trees.behaviours.Success` fallback at line 683 enforces this contract
- `vultron/core/behaviors/embargo/nodes.py` — line 265: same "non-fatal" pattern in embargo broadcast path
- Two independent broadcast sites suggest fan-out delivery is not yet centralized, making a systematic fix harder

## Impact if Ignored

Peers receive no notification when a broadcast fails, so state silently diverges. There is no retry, dead-letter queue, or observability mechanism. In a federated protocol whose purpose is to synchronize independent actors around a shared case log, undetected delivery failure is a top-level correctness risk.

## Suggested Action

1. Change broadcast nodes to return `FAILURE` on delivery errors so the parent BT can react (retry, alert, or abort the workflow).
2. Centralize all peer fan-out broadcast logic into a single shared module so retry and dead-letter support can be added in one place rather than patched at each call site.
3. Evaluate whether a dead-letter or at-least-once delivery guarantee is needed at the protocol level (relates to #766 — Federation & Delivery Infrastructure).

**Resolved**: 2026-06-08 — implementation tracked in #834, #835.
Docs PR: [#833](https://github.com/CERTCC/Vultron/pull/833).
Spec: `specs/behavior-tree-integration.yaml`.
Notes: `notes/peer-broadcast-failure-semantics.md`.
