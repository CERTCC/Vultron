---
title: "EMBARGO-DUR-1 \u2014 EmbargoPolicy ISO 8601 Duration Fields (2026-04-09)"
type: implementation
timestamp: '2026-04-08T00:00:00+00:00'
source: EMBARGO-DUR-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 5083
legacy_heading: "EMBARGO-DUR-1 \u2014 EmbargoPolicy ISO 8601 Duration Fields\
  \ (2026-04-09)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-09'
---

## EMBARGO-DUR-1 — EmbargoPolicy ISO 8601 Duration Fields (2026-04-09)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:5083`
**Canonical date**: 2026-04-08 (git blame)
**Legacy heading**

```text
EMBARGO-DUR-1 — EmbargoPolicy ISO 8601 Duration Fields (2026-04-09)
```

**Legacy heading dates**: 2026-04-09

**Task**: EMBARGO-DUR-1 (Priority 310)

**Summary**: Updated `EmbargoPolicy` Pydantic model to use ISO 8601 duration
strings (e.g. `"P90D"`) at the wire layer, with `datetime.timedelta` as the
internal representation, per `specs/embargo-policy.yaml` EP-01-002/003 and
`specs/duration.yaml` DUR-01-001, DUR-04-001, DUR-05-001, DUR-05-002.

### What was done

- **`vultron/wire/as2/vocab/objects/embargo_policy.py`**: Replaced integer
  `preferred_duration_days`, `minimum_duration_days`, `maximum_duration_days`
  fields with `preferred_duration`, `minimum_duration`, `maximum_duration`
  typed as `timedelta` / `timedelta | None`. Added `_parse_duration()` helper
  using `isodate` that rejects calendar units (years, months, weeks per
  DUR-04-001) and malformed strings (DUR-04-002). A `field_validator` and
  `field_serializer` pair handles ISO 8601 ↔ `timedelta` conversion.
- **`vultron/core/behaviors/case/nodes.py`**: `InitializeDefaultEmbargoNode`
  now reads `preferred_duration` (ISO 8601 string) from the stored policy
  dict and parses it via `isodate`. Falls back to 90-day default if the field
  is absent, unparseable, or uses calendar units.
- **`test/wire/as2/vocab/test_embargo_policy.py`**: Full rewrite to use ISO
  8601 strings and `timedelta` comparisons. Added 20 new tests covering
  DUR-04-001 (reject Y/M/W), DUR-04-002 (reject malformed), DUR-04-003
  (reject empty), DUR-05-001/002 (timedelta internal, ISO 8601 JSON), and
  round-trip serialization via `object_to_record` and `TinyDbDataLayer`.
- **`test/wire/as2/vocab/test_vultron_actor.py`**: Updated `_make_policy()`
  to use `timedelta()` values.

### Validation

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1282 passed, 5581 subtests passed in 30.94s`
