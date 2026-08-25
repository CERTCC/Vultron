---
name: 2607-ratchet-ceiling-stale
description: Pre-existing CI failure on origin/main — spec coverage ratchet ceiling stale (948 > 947)
metadata:
  type: project
---

**Bug #2607**: `test_protocol_spec_coverage_floor` fails on `origin/main` — uncovered count 948 exceeds ceiling 947.

**Why:** A protocol-kind spec was added (or coverage mapping removed) without tightening the ratchet. Discovered during task/1932 validation on 2026-08-25.

**How to apply:** Any PR CI run will show this failure until #2607 is fixed. Note it as pre-existing when filing PRs that hit this failure.
