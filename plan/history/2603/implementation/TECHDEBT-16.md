---
title: "TECHDEBT-16 \u2014 DRY core domain models: VultronObject base class\
  \ (2026-03-18)"
type: implementation
date: '2026-03-17'
source: TECHDEBT-16
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1802
legacy_heading: "TECHDEBT-16 \u2014 DRY core domain models: VultronObject\
  \ base class (2026-03-18)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-18'
---

## TECHDEBT-16 — DRY core domain models: VultronObject base class (2026-03-18)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1802`
**Canonical date**: 2026-03-17 (git blame)
**Legacy heading**

```text
TECHDEBT-16 — DRY core domain models: VultronObject base class (2026-03-18)
```

**Legacy heading dates**: 2026-03-18

Added `VultronObject` base class to `vultron/core/models/base.py`. This class
captures the three fields shared by all domain object models: `as_id` (with
`_new_urn` factory default), `as_type` (required; subclasses provide defaults),
and `name` (`str | None = None`). Mirrors the `as_Base`/`as_Object` hierarchy
in the wire layer.

All 12 concrete domain object classes now inherit from `VultronObject`:
`VultronReport`, `VultronCase`, `VultronNote`, `VultronParticipant`,
`VultronParticipantStatus`, `VultronCaseStatus`, `VultronEmbargoEvent`,
`VultronCaseActor`, `VultronActivity`, `VultronOffer`, `VultronAccept`,
`VultronCreateCaseActivity`.

Repeated `as_id` and `name` field definitions removed from all 12 classes.
`as_type` remains in each subclass with its specific default (or required in
`VultronActivity`). Unused `BaseModel`, `Field`, and `_new_urn` imports cleaned
up from affected modules.

`VultronEvent` (events/base.py) was intentionally excluded — it represents an
inbound domain message envelope with different semantics (`activity_id`,
`semantic_type`) rather than a persistent domain object.

`vultron/core/models/__init__.py` updated to export `VultronObject`.

New tests added in `test/core/models/test_base.py` verifying inheritance,
`as_id` generation, `as_type` defaults, and `name` field presence for all
12 domain object classes.

**Test results:** 961 passed (+48), 5581 subtests, 0 failed.
