---
source: ISSUE-750
timestamp: '2026-06-08T14:39:40.534719+00:00'
title: InitializeDefaultEmbargoNode subtree decomposition
type: implementation
---

## Issue #750 — God node decomposition: split InitializeDefaultEmbargoNode into composed subtree (after #538)

Implemented a composed subtree for default embargo initialization by replacing the monolithic node with five named leaves: duration resolution, embargo creation, lifecycle proposal, case attachment, and owner-signatory seeding.

The new flow delegates embargo proposal transitions to EmbargoLifecycle in STRICT mode, preserves existing idempotent behavior for duplicate runs, and keeps event and participant side effects aligned with existing case-creation and duplicate-report expectations.

PR: <https://github.com/CERTCC/Vultron/pull/827>
