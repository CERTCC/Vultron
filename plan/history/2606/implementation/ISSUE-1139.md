---
source: ISSUE-1139
timestamp: '2026-06-25T17:52:29.314952+00:00'
title: 'CP-05-005 (part 2): Background retry runner for pending Create(VulnerabilityCase)'
type: implementation
---

## Issue #1139 — CP-05-005 (part 2): Background retry runner for pending Create(VulnerabilityCase) activities

Implemented the background retry runner for persisted PendingCreateCaseActivity
markers (CP-05-005, part 2 of 2). This completes the durable-delivery guarantee for
the Accept(CaseProposal) -> Create(VulnerabilityCase) two-activity sequence.

What was built:

- vultron/adapters/driving/fastapi/pending_retry.py: Core retry runner with
  retry_pending_create_case_activities(). Scans all actor DataLayers for
  PendingCreateCaseActivity markers, reconstructs the pre-built
  Create(VulnerabilityCase) payload (preserving the original id_), persists
  it if absent (idempotency), enqueues it with an outbox-existence check before
  record_outbox_item (prevents duplicate entries when marker deletion fails),
  and deletes the marker on success.

- vultron/adapters/driving/fastapi/app.py: Wired the retry runner into the
  configure_globals=True lifespan path, called after OutboxMonitor.start().

- test/adapters/driving/fastapi/test_pending_retry.py: 16 tests covering all
  ACs including the stuck-marker path (AC-4) and full integration scenario (AC-5).

Design decision (AC-2): On-startup scan (option a) was chosen. The
OutboxMonitor is already running when the scan fires, so re-queued activities
drain without an extra signal. No ongoing polling overhead.

Key code review finding fixed: record_outbox_item has no uniqueness
constraint -- a stuck marker (delete fails) would cause double delivery on the
next startup. Added an outbox-existence guard before enqueuing.

PR: [#1180](https://github.com/CERTCC/Vultron/pull/1180)
