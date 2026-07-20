---
source: ISSUE-1528
timestamp: '2026-07-20T14:38:38.382272+00:00'
title: 'specs: fix render_for_kind kind-routing and add kind-drift linter'
type: implementation
---

## Issue #1528 — fix render_for_kind kind-routing and flatten kind to item level

Implemented effective-kind routing in the spec docs renderer and flattened `kind` to be
required on every individual spec item (removing file/group-level inheritance).

**Changes:**

- `render_for_kind()` routes by per-item `kind` (SR-09-001/SR-09-002): groups appear on
  each kind page for which they have matching items; non-matching items suppressed
- All ~60 `specs/*.yaml` files audited bottom-up; `kind` stamped on all 1996 spec items
  and file/group-level `kind` fields removed (AC-2 through AC-5)
- `kind` field made required (non-optional) on `StatementSpec`/`BehavioralSpec`; Pydantic
  validates at load time — `_check_missing_kind` in linter provides belt-and-suspenders
  hard-error exit-1 (SR-09-003)
- `effective_kind()` removed from registry; `spec.kind` used directly everywhere
- 8 new tests covering SR-09-001/002 routing and SR-09-003 missing-kind hard error

**PR:** <https://github.com/CERTCC/Vultron/pull/1530>
