---
source: ISSUE-1374
timestamp: '2026-07-13T20:53:00.685179+00:00'
title: Fix MoreVendors/MoreCoordinators exhaustion loop
type: implementation
---

## Issue #1374 — FUZZ-08e-follow: Fix IdentifyVendors/IdentifyCoordinators exhaustion loop

Replaced purely probabilistic MoreVendors (25%) and MoreCoordinators (10%) guards with
blackboard-driven exhaustion checks. InjectVendor and InjectCoordinator now pop one entry
per tick from identified_vendors / identified_coordinators and append to
potential_participants. Probabilistic fallback preserved when key is absent or list is empty.

PR: <https://github.com/CERTCC/Vultron/pull/1399>

158 tests pass in target module (+98 new). All linters clean.
