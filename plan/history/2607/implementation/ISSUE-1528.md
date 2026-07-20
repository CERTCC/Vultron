---
source: ISSUE-1528
timestamp: '2026-07-20T14:38:38.382272+00:00'
title: 'specs: fix render_for_kind kind-routing and add kind-drift linter'
type: implementation
---

## Issue #1528 — fix render_for_kind kind-routing and add kind-drift linter

Implemented effective-kind routing in the spec docs renderer and a new kind-drift linter check.

**Changes:**

- `render_for_kind()` now routes by effective kind (SR-09-001/SR-09-002): files appear on all kind pages where they have matching items; non-matching items in mixed-kind groups are suppressed
- New `LintWarningCode.KIND_DRIFT` and `_check_kind_drift()` emit advisory warnings when group kind diverges from majority item kind, or file kind diverges from majority group kind (SR-09-003/SR-09-004); suppressible via `lint_suppress: [kind_drift]`
- 12 new tests covering all four SRs

**PR:** <https://github.com/CERTCC/Vultron/pull/1530>
