---
title: "TECHDEBT-35 \u2014 VultronEvent rich-object architectural fix"
type: implementation
timestamp: '2026-03-24T00:00:00+00:00'
source: TECHDEBT-35
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3019
legacy_heading: "TECHDEBT-35 \u2014 VultronEvent rich-object architectural\
  \ fix"
date_source: git-blame
---

## TECHDEBT-35 — VultronEvent rich-object architectural fix

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3019`
**Canonical date**: 2026-03-24 (git blame)
**Legacy heading**

```text
TECHDEBT-35 — VultronEvent rich-object architectural fix
```

**Completed**: PRIORITY-80 phase.

### Problem

`VultronEvent` was designed to be the core-layer parallel of AS2 `Activity`
(as rich structurally), but was implemented as a flat DTO carrying only ID
strings (`object_id`, `target_id`, etc.). Concrete subclasses layered typed
domain object fields (`report: VultronReport`, `case: VultronCase`, etc.)
alongside the flat ID fields — two parallel representations that prevented the
mixins from providing clean rich-object access.

### Changes

- **`vultron/core/models/events/base.py`**: Replaced 14 flat ID/type string
  fields on `VultronEvent` with 7 rich `VultronObject | None` fields:
  `object_`, `target`, `context`, `origin`, `inner_object`, `inner_target`,
  `inner_context`. Added derived `@property` for all 14 old fields (backward
  compat for use-case code). `object_` uses a trailing underscore because
  `object` is a Python built-in.

- **`vultron/core/models/events/_mixins.py`**: Added rich `foo` property to
  every mixin alongside the existing `foo_id` property. Properties access
  `self.object_`, `self.target`, `self.context`, etc. with domain-typed hints
  under `TYPE_CHECKING`. Added `from __future__ import annotations` to support
  forward references.

- **Concrete event subclasses** (`report.py`, `case.py`, `embargo.py`,
  `note.py`, `status.py`, `case_participant.py`, `actor.py`): Removed all
  explicit typed domain object fields (`report: VultronReport`,
  `case: VultronCase`, `embargo: VultronEmbargoEvent`, `participant`,
  `note`, `status`). These are now provided by mixin properties. Kept
  explicit `activity: VultronActivity` redeclarations on subclasses that
  require it (existing approach, no `HasActivityMixin` introduced).

- **`vultron/wire/as2/extractor.py`**: Updated `_build_domain_kwargs()` to
  populate `object_=<domain obj>` instead of per-semantic keys (`report=`,
  `case=`, `embargo=`, etc.). Added `_to_domain_obj()` helper to wrap bare
  AS2 references as minimal `VultronObject` instances. Updated the constructor
  call to use the new rich field names; removed all flat `_id`/`_type` kwargs.

- **`test/core/use_cases/test_report_use_cases.py`**: Updated 3 event
  constructor calls from `object_id=..., report=VultronReport(...)` style
  to `object_=VultronReport(...)`.

### Test results

988 passed, 5581 subtests passed.
