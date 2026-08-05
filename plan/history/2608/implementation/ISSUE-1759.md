---
source: ISSUE-1759
timestamp: '2026-08-05T23:20:50.833207+00:00'
title: 'fix(fvcv-handoff-demo): correct case closure ordering'
type: implementation
---

## Issue #1759 — fix(fvcv-handoff-demo): correct case closure ordering — Coordinator closes last

Reordered Phase 7 `actor_closes_case` calls in `_phase_case_closure` so Coordinator (the case owner) closes after Vendor1, Vendor2, and Finder. Previously the order was Vendor1 → Vendor2 → Coordinator → Finder; corrected to Vendor1 → Vendor2 → Finder → Coordinator.

Added `test_phase_case_closure_coordinator_closes_last` to assert the ordering invariant.

PR: <https://github.com/CERTCC/Vultron/pull/2021>
