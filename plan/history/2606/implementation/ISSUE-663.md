---
source: ISSUE-663
timestamp: '2026-06-02T20:06:57.732305+00:00'
title: Prevent status self-broadcast loops
type: implementation
---

## Issue #663 — BroadcastStatusToPeersNode: participants re-broadcast to themselves (self-loop)

Fixed `BroadcastStatusToPeersNode` so the current actor is excluded from the recipient list, preventing participant self-broadcast loops while preserving normal fan-out to other peers.

PR: [#677](https://github.com/CERTCC/Vultron/pull/677)
