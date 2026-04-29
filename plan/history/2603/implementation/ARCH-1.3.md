---
title: 'ARCH-1.3 complete: wire/as2/parser.py and wire/as2/extractor.py created'
type: implementation
date: '2026-03-09'
source: ARCH-1.3
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 763
legacy_heading: "2026-03-09 \u2014 ARCH-1.3 complete: wire/as2/parser.py and\
  \ wire/as2/extractor.py created"
date_source: git-blame
legacy_heading_dates:
- '2026-03-09'
---

## ARCH-1.3 complete: wire/as2/parser.py and wire/as2/extractor.py created

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:763`
**Canonical date**: 2026-03-09 (git blame)
**Legacy heading**

```text
2026-03-09 — ARCH-1.3 complete: wire/as2/parser.py and wire/as2/extractor.py created
```

**Legacy heading dates**: 2026-03-09

### What moved

- **`vultron/wire/as2/parser.py`** (new): `parse_activity()` extracted from
  `vultron/api/v2/routers/actors.py`. Raises domain exceptions (`VultronParseError`
  hierarchy defined in `vultron/wire/as2/errors.py` and `vultron/wire/errors.py`)
  instead of `HTTPException`. The router now has a thin HTTP adapter wrapper that
  catches these and maps to 400/422 responses (R-03, V-06, ARCH-08-001).

- **`vultron/wire/as2/extractor.py`** (new): Consolidates `ActivityPattern` class,
  all 37 pattern instances, `SEMANTICS_ACTIVITY_PATTERNS` dict, and
  `find_matching_semantics()` from the former `vultron/activity_patterns.py` and
  `vultron/semantic_map.py`. This is now the sole location for AS2-to-domain
  semantic mapping (R-04, V-05, ARCH-03-001).

- **`vultron/wire/errors.py`** (new): `VultronWireError(VultronError)` base.
- **`vultron/wire/as2/errors.py`** (new): `VultronParseError`, subtypes for missing
  type, unknown type, and validation failure.

### Backward-compat shims retained

`vultron/activity_patterns.py` and `vultron/semantic_map.py` converted to
re-export shims so any external code importing from the old locations continues
to work. These can be deleted once confirmed no external callers remain.

### What else changed

- `vultron/behavior_dispatcher.py`: import `find_matching_semantics` from
  `vultron.wire.as2.extractor` (no longer `vultron.semantic_map`).
- `vultron/api/v2/backend/inbox_handler.py`: removed `raise_if_not_valid_activity`
  (V-07) and the `VOCABULARY` import; activity type validation now happens
  entirely in the wire parser layer before the item reaches the inbox handler.
- Tests: `test_raise_if_not_valid_activity_raises` deleted; 7 new wire layer tests
  added in `test/wire/as2/`. 822 tests pass (up from 815).
