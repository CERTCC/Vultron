---
source: ISSUE-755
timestamp: '2026-06-10T16:18:25.093604+00:00'
title: SYNC BT god-node decomposition for replay/fan-out/hash-check
type: implementation
---

## Issue #755 — God node decomposition: split ReplayMissingEntriesNode, FanOutLogEntryNode, and CheckHashOrRejectOnMismatchNode

Decomposed three SYNC behavior nodes into explicit composite trees with named leaf nodes:

- `ReplayMissingEntriesNode` now delegates to collect/sort, divergence-find, and send leaves.
- `FanOutLogEntryNode` now delegates to recipient-collection and send leaves.
- `CheckHashOrRejectOnMismatchNode` now delegates to a pure hash-check condition and a reject action leaf.

Added node-level tests covering composite structure, blackboard wiring, send behavior, and selector short-circuit behavior.

PR: <https://github.com/CERTCC/Vultron/pull/871>
