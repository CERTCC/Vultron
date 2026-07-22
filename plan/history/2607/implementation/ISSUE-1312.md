---
source: ISSUE-1312
timestamp: '2026-07-22T19:00:49.561199+00:00'
title: 'FUZZ-08d: Publish leaf → draft-review-submit pipeline (Production Collapse
  4)'
type: implementation
---

## Issue #1312 — FUZZ-08d: Publish leaf → draft-review-submit pipeline (Production Collapse 4)

Implemented Production Collapse 4 (ADR-0030 / BT-20-004). Replaced the single `Publish` Actuator
leaf in each per-artifact arm of `create_publication_tree` with a four-step pipeline:
DraftAdvisoryArtifact → ReviewAdvisoryDraft → optional ReviseAdvisoryDraft → SubmitAdvisoryArtifact.

New module `publish_artifact_tree.py` with `AdvisoryReviewDecision`, `_NeedsRevisionGate`, and
`create_publish_artifact_tree()`. Four new fuzzer nodes added to `publication.py`.
`publication_tree.py` `publish_factory` parameter removed and replaced with four pipeline factory
parameters. ADR-0030 accepted. BT-20-004 PROVISIONAL marker removed.

All 5385 tests pass. PR: <https://github.com/CERTCC/Vultron/pull/1617>
