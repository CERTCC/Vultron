---
title: "TECHDEBT-32 / TECHDEBT-32b \u2014 DataLayer boundary audit and core\
  \ adapter import removal"
type: implementation
timestamp: '2026-03-24T00:00:00+00:00'
source: LEGACY-2026-03-24-techdebt-32-techdebt-32b-datalayer-boundary-audi
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2869
legacy_heading: "TECHDEBT-32 / TECHDEBT-32b \u2014 DataLayer boundary audit\
  \ and core adapter import removal (COMPLETE 2026-03-24)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-24'
---

## TECHDEBT-32 / TECHDEBT-32b — DataLayer boundary audit and core adapter import removal

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2869`
**Canonical date**: 2026-03-24 (git blame)
**Legacy heading**

```text
TECHDEBT-32 / TECHDEBT-32b — DataLayer boundary audit and core adapter import removal (COMPLETE 2026-03-24)
```

**Legacy heading dates**: 2026-03-24

### What was done

**TECHDEBT-32 (research)**: Audited the `core`/`DataLayer` boundary for layer
violations. Findings written to `notes/datalayer-refactor.md`.

Key findings:

1. **Core violations** (CS-05-001): `vultron/core/use_cases/triggers/embargo.py`
   and `vultron/core/use_cases/triggers/_helpers.py` both imported
   `object_to_record` from `vultron.adapters.driven.db_record`. 5 call sites
   used `dl.update(obj.as_id, object_to_record(obj))`.
2. **Redundant core helper**: `save_to_datalayer()` in
   `vultron/core/behaviors/helpers.py` duplicated `dl.save()` using
   `StorableRecord`; used in BT nodes (`case/nodes.py`, `report/nodes.py`).
3. **Wire violation** (separate task TECHDEBT-32c): `rehydration.py` imports
   `get_datalayer` from the TinyDB adapter as a fallback.
4. `Record`/`StorableRecord` hierarchy is architecturally sound — no changes
   needed. `find_in_vocabulary` usages are all in adapter or wire layers.

**TECHDEBT-32b (code fix)**: Standardised on `dl.save(obj)` across all core code:

- Removed `object_to_record` import from `triggers/embargo.py` and
  `triggers/_helpers.py`. Replaced 5 `dl.update(..., object_to_record(...))` calls
  with `dl.save(obj)`.
- Replaced 4 `save_to_datalayer(self.datalayer, obj)` calls in BT nodes
  (`case/nodes.py`, `report/nodes.py`) with `self.datalayer.save(obj)`.
- Deleted `save_to_datalayer()` function from `helpers.py`.
- Removed now-unused `BaseModel` import from `helpers.py`.
- Added TECHDEBT-32c to plan for remaining wire-imports-adapter violation in
  `rehydration.py`.

### Lessons learned

The three `dl.save()` patterns (`object_to_record` + `dl.update`, `save_to_datalayer`,
and direct `dl.save`) all existed simultaneously, causing confusion. `dl.save()`
is now the canonical single pattern for persisting domain objects from core code.

### Test results

985 passed, 5581 subtests passed.
