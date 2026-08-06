---
source: ISSUE-1758
timestamp: '2026-08-05T23:21:12.786503+00:00'
title: 'fix(fvcv-handoff-demo): correct Phase 6 publication order'
type: implementation
---

## Issue #1758 — fix(fvcv-handoff-demo): correct publication ordering

Reordered Phase 6 `actor_notifies_published` calls in `_phase_publication` to realistic CVD order: Vendor1 → Vendor2 → Finder → Coordinator. The previous code called Coordinator first — before other participants — which is wrong because only the CASE_OWNER's (Coordinator's) `notify-published` triggers embargo teardown (DEMOMA-07-003 step 4).

Added `test_phase_publication_order_vendor1_vendor2_finder_coordinator` to assert the exact call order.

PR: <https://github.com/CERTCC/Vultron/pull/2022>
