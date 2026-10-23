---
title: "VCR-020/021a/021b/022/029 \u2014 VultronEvent activity field and docstring\
  \ cleanup (2026-03-19)"
type: implementation
timestamp: '2026-03-19T00:00:00+00:00'
source: LEGACY-2026-03-19-vcr-020-021a-021b-022-029-vultronevent-activity
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2344
legacy_heading: "VCR-020/021a/021b/022/029 \u2014 VultronEvent activity field\
  \ and docstring cleanup (2026-03-19)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-19'
---

## VCR-020/021a/021b/022/029 — VultronEvent activity field and docstring cleanup (2026-03-19)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2344`
**Canonical date**: 2026-03-19 (git blame)
**Legacy heading**

```text
VCR-020/021a/021b/022/029 — VultronEvent activity field and docstring cleanup (2026-03-19)
```

**Legacy heading dates**: 2026-03-19

**Tasks completed**: VCR-020, VCR-021a, VCR-021b, VCR-022, VCR-029

### What was done

**VCR-020**: Added `activity: VultronActivity | None = None` to `VultronEvent`
in `vultron/core/models/events/base.py`. This satisfies ARCH-10-001 (fail-fast
domain objects): the base class permits `None` for semantics that don't use the
full activity object; the 12 concrete subclasses that always carry an activity
already narrowed the field to required by declaring `activity: VultronActivity`
without a default. The base class now imports `VultronActivity` from
`vultron.core.models.activity` (no circular imports).

**VCR-021a**: Clarified the distinction between `VultronActivity` and
`VultronEvent` in their docstrings. `VultronActivity` is the domain model for
AS2 activity objects stored in the DataLayer; `VultronEvent` is the semantic
dispatch event carrying decomposed ID/type fields used for handler routing.
A `VultronEvent` may carry a `VultronActivity` as its `activity` field, but
the two types serve different purposes.

**VCR-021b / VCR-029**: Verified all concrete domain object fields in event
subclasses (`report`, `case`, `embargo`, `participant`, `note`, `status`,
`activity`) are already non-optional where the value is always present. No
code changes required for these two tasks.

**VCR-022**: Verified as equivalent to TECHDEBT-16 (already complete).
`VultronObject` base class exists in `vultron/core/models/base.py` and all
10 domain object model classes inherit from it.

**Result**: 982 tests pass, 5 warnings unchanged.
