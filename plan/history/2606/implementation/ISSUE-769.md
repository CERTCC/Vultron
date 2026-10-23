---
source: ISSUE-769
timestamp: '2026-06-08T15:11:44.323963+00:00'
title: InboxPipeline test seam and routing safety-net
type: implementation
---

## Issue #769 — Implement InboxPipeline to surface inbox→dispatcher seam as testable unit

Implemented an injectable InboxPipeline in the FastAPI driving adapter with full single-item processing (rehydrate, semantic extraction, defer-or-dispatch, replay handling) and a build_test_pipeline factory wired with the production dispatcher map.

Added test_pipeline fixture support and new routing safety-net tests covering report, case, embargo, note, actor, status, and sync semantic domains, plus a deferral-path assertion for unknown case context.

PR: [#830](https://github.com/CERTCC/Vultron/pull/830)
