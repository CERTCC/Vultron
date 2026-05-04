---
title: "WIRE-TRANS-04 + WIRE-TRANS-05 \u2014 Activity wire base + delete serializer.py"
type: implementation
timestamp: '2026-04-15T00:00:00+00:00'
source: LEGACY-2026-04-15-wire-trans-04-wire-trans-05-activity-wire-base-d
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6345
legacy_heading: "WIRE-TRANS-04 + WIRE-TRANS-05 \u2014 Activity wire base +\
  \ delete serializer.py"
date_source: git-blame
---

## WIRE-TRANS-04 + WIRE-TRANS-05 — Activity wire base + delete serializer.py

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6345`
**Canonical date**: 2026-04-15 (git blame)
**Legacy heading**

```text
WIRE-TRANS-04 + WIRE-TRANS-05 — Activity wire base + delete serializer.py
```

**Tasks**: WIRE-TRANS-04, WIRE-TRANS-05 (Priority 340)

**What was done**:

- **WIRE-TRANS-04**: Created `vultron/wire/as2/vocab/activities/base.py`
  containing `VultronAS2Activity(as_TransitiveActivity)`. The class provides a
  generic `from_core(cls, domain_activity: VultronActivity) -> VultronAS2Activity`
  classmethod that converts a domain activity via JSON round-trip
  (`model_dump(mode="json")` + `model_validate`), with optional `_field_map`
  rename support for subclasses. Subclasses narrow the parameter type annotation.
  The module is auto-discovered by the existing `activities/__init__.py` package
  discovery mechanism.
- **WIRE-TRANS-05**: Deleted `vultron/wire/as2/serializer.py` (6 unused
  `domain_xxx_to_wire()` functions; confirmed zero callers in codebase).
- Added 4 tests to `test/wire/as2/vocab/test_wire_domain_translation.py`
  covering: string-field activity, None-object activity, `_field_map` rename
  subclass, and Accept domain subtype.

**Validation**:

- `uv run black vultron/ test/`
- `uv run flake8 vultron/ test/`
- `uv run mypy` → `Success: no issues found in 501 source files`
- `uv run pyright` → `0 errors, 0 warnings, 0 informations`
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1430 passed, 12 skipped, 182 deselected, 5581 subtests passed in 19.30s`
