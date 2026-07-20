---
source: ISSUE-680
timestamp: '2026-07-20T19:16:10.136629+00:00'
title: Add queue-depth observability to OutboxMonitor
type: implementation
---

## Issue #680 — Add queue-depth observability to OutboxMonitor

Extends `OutboxMonitor.drain_all()` with two levels of observability:

- DEBUG-level drain-pass summary (total pending items across all actors) on every pass — OX-09-004
- WARNING per actor when outbox depth exceeds configurable `depth_warn_threshold` — OX-09-005

Also adds `depth_warn_threshold` parameter with negative-value guard, refactors `drain_all()` to call `outbox_list()` once per actor (snapshot into `depths` dict), and hoists pre-existing inline imports to module level.

8 new tests; 37 total pass. All linters clean.

PR: <https://github.com/CERTCC/Vultron/pull/1542>
