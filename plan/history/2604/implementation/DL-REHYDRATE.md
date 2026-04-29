---
title: 'DL-REHYDRATE: DataLayer semantic type recovery'
type: implementation
date: '2026-04-17'
source: DL-REHYDRATE
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6595
legacy_heading: 'DL-REHYDRATE: DataLayer semantic type recovery'
date_source: git-blame
---

## DL-REHYDRATE: DataLayer semantic type recovery

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6595`
**Canonical date**: 2026-04-17 (git blame)
**Legacy heading**

```text
DL-REHYDRATE: DataLayer semantic type recovery
```

**Task**: PRIORITY-345 DL-REHYDRATE
**Completed**: 2026-05-20

### Summary

Implemented automatic field rehydration and semantic-class coercion in
`SqliteDataLayer._from_row` so that `dl.read()` always returns fully-typed
domain objects without requiring manual coercion in use cases.

### Changes

**`vultron/adapters/driven/datalayer_sqlite.py`**:

- Added `_rehydrate_fields()`: expands dehydrated string-ID fields
  (`object_`, `target`, `origin`, `result`, `instrument`) back to typed
  Pydantic objects via `self.read()`.
- Added `_coerce_to_semantic_class()`: pattern-matches rehydrated activities
  against `SEMANTICS_ACTIVITY_PATTERNS` and coerces to the most specific
  Python class registered in `SEMANTICS_TO_ACTIVITY_CLASS`.
- Updated `_from_row` to call both methods after `record_to_object`.

**`vultron/wire/as2/extractor.py`**:

- Added imports for all specific activity classes.
- Added `SEMANTICS_TO_ACTIVITY_CLASS: dict[MessageSemantics, type[as_Activity]]`
  with 34 entries — maps each semantic type to its specific Python class.

**`vultron/core/models/protocols.py`**:

- Added `model_copy` to `PersistableModel` Protocol to match Pydantic v2
  signature (`Mapping[str, Any] | None`).

**`vultron/core/use_cases/triggers/embargo.py`**:

- Removed large manual coercion block (previously lines 210-247) that
  dehydrated `EmProposeEmbargoActivity.object_` strings; replaced with a
  simple `isinstance` check since `dl.read()` now returns the correct type.
- Simplified `embargo is None` check by removing the `type_` string guard.

**`vultron/core/use_cases/triggers/report.py`**:

- Removed `rehydrate`, `as_Object`, and `PydanticValidationError` imports.
- Simplified `_resolve_offer_and_report` from 37 lines to 12 lines; now
  directly checks `isinstance(offer, RmSubmitReportActivity)` and
  `isinstance(report, VulnerabilityReport)`.

**`test/adapters/driven/test_sqlite_backend.py`**:

- Updated `test_reading_activity_back_yields_id_string_for_nested_object` →
  `test_reading_activity_back_yields_expanded_nested_object` to reflect new
  behavior.
- Added `TestRehydrateFields` and `TestCoerceToSemanticClass` test classes
  covering the round-trip for `RmSubmitReportActivity` and
  `EmProposeEmbargoActivity`.

**`test/core/behaviors/report/test_prioritize_tree.py`**,
**`test/core/use_cases/received/test_actor.py`**:

- Updated assertions from `object_ == case.id_` to `object_.id_ == case.id_`
  since `engage_activity.object_` is now a typed `VulnerabilityCase` object.

### Test results at completion

1619 passed, 12 skipped, 182 deselected, 5581 subtests; `black`, `flake8`,
`mypy`, `pyright` all clean.
