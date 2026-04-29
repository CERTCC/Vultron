---
title: "PRIORITY-348 DR-01 + DR-02 \u2014 Outbox reference dehydration and\
  \ activity name fix"
type: implementation
date: '2026-04-20'
source: LEGACY-2026-04-20-priority-348-dr-01-dr-02-outbox-reference-dehydr
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7098
legacy_heading: "PRIORITY-348 DR-01 + DR-02 \u2014 Outbox reference dehydration\
  \ and activity name fix"
date_source: git-blame
---

## PRIORITY-348 DR-01 + DR-02 — Outbox reference dehydration and activity name fix

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7098`
**Canonical date**: 2026-04-20 (git blame)
**Legacy heading**

```text
PRIORITY-348 DR-01 + DR-02 — Outbox reference dehydration and activity name fix
```

**Date:** 2026-04-20

### DR-01 — Outbox reference-field dehydration

**Problem:** `handle_outbox_item()` in `outbox_handler.py` converts typed AS2
activities (e.g. `RmInviteToCaseActivity`) to `VultronActivity` via
`model_dump(by_alias=True)` + `VultronActivity.model_validate()`. Trigger
use cases may set reference fields (e.g. `target`) to full domain objects
(e.g. a `VulnerabilityCase`). Since `VultronActivity.target: NonEmptyString | None`,
validation failed with a type error.

**Fix:** Added `_dehydrate_references(activity_dict: dict) -> dict` to
`outbox_handler.py`. Collapses dict-valued reference fields to URI strings
by preferring `href` (AS2 Link) then `id`. Handles list fields element-wise.
Fields dehydrated: `actor`, `target`, `to`, `cc`, `bto`, `bcc`, `origin`,
`result`, `instrument`. `"object"` is explicitly exempt (must stay inline).
Applied to the raw `model_dump()` dict before `VultronActivity.model_validate()`.

### DR-02 — Activity `name` repr bug

**Problem:** `as_TransitiveActivity.set_name()` constructed the activity `name`
using `str(self.target)` etc., which produced Python Pydantic repr strings
(e.g. `"type_=<VultronObjectType.VULNERABILITY_CASE: 'VulnerabilityCase'>..."`)
for domain objects. Also, `name_of()` returned the string `"None"` when
`obj.name` was `None`, rather than falling back to a meaningful ID.

**Fix (two parts):**

1. Updated `name_of()` in `vultron/wire/as2/vocab/base/utils.py`:
   now returns strings directly, falls back to `href` (links), then `id_`,
   then `str(obj)`. Never returns `"None"` for objects with `id_`.
2. Applied `name_of()` consistently in `as_TransitiveActivity.set_name()`
   for `origin`, `target`, and `instrument` fields (was using raw `str()`
   conversion before).

**Files changed:**

- `vultron/adapters/driving/fastapi/outbox_handler.py`: `_dehydrate_references()` + application
- `vultron/wire/as2/vocab/base/utils.py`: updated `name_of()`
- `vultron/wire/as2/vocab/base/objects/activities/transitive.py`: `set_name()` fix
- `test/adapters/driving/fastapi/test_outbox.py`: regression + unit tests for DR-01
- `test/wire/as2/vocab/test_base_utils.py`: tests for `name_of()` and `set_name()`

**Test Result:**

1689 passed, 12 skipped, 182 deselected, 5581 subtests passed
