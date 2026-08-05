---
title: fvcv_extension_demo and fccv_handoff_demo have same wrong case closure ordering
type: learning
timestamp: 2026-08-05
source: ISSUE-1759
signal: concern
---

While fixing the closure ordering in `fvcv_handoff_demo.py` (ISSUE-1759), the same
ordering bug was observed in two peer scenarios:

- `vultron/demo/scenario/fvcv_extension_demo.py` — Phase 7 closes:
  Vendor1 → Vendor2 → Coordinator → Finder (Coordinator before Finder)
- `vultron/demo/scenario/fccv_handoff_demo.py` — Phase 7 closes:
  c1 → c2 → Vendor → Finder (Vendor before Finder, where c1/c2 are coordinators)

The CVD protocol principle — case owner closes last — applies equally to these
scenarios. Both should be fixed with the same reorder pattern applied in #2021.

Suggested follow-up: create a GitHub issue (or sub-issues of Epic #1753) to fix
the same ordering bug in the extension and fccv_handoff demos.
