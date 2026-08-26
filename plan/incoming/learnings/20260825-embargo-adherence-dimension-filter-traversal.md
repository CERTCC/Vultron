---
title: "embargo_adherence @computed_field adds double-traversal in dimension_filter.py"
type: learning
timestamp: "2026-08-25"
source: ISSUE-2189
signal: concern
---

In `vultron/core/behaviors/status/nodes/dimension_filter.py`, line 149 already reads `status.consent.state` for the PEC slot, and line 151 reads `status.embargo_adherence`, which re-traverses `consent` and `consent.state` via the `@computed_field` property. Before issue #2189 this was a single O(1) slot read; after it is two attribute hops per filter-loop iteration.

For the current codebase this is micro-overhead, but it is a regression from the stored-field implementation. A follow-up could either:

1. Cache `status.embargo_adherence` in a local variable before building the tuple, or
2. Reuse the already-computed consent-state from line 149: `consent.state == PEC.SIGNATORY`.

This was identified by the efficiency review agent during the simplify phase of ISSUE-2189.
