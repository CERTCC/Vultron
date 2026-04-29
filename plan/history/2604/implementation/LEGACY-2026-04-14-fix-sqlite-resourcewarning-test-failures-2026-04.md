---
title: 'Fix: SQLite ResourceWarning Test Failures (2026-04-14)'
type: implementation
date: '2026-04-14'
source: LEGACY-2026-04-14-fix-sqlite-resourcewarning-test-failures-2026-04
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6071
legacy_heading: 'Fix: SQLite ResourceWarning Test Failures (2026-04-14)'
date_source: git-blame
legacy_heading_dates:
- '2026-04-14'
---

## Fix: SQLite ResourceWarning Test Failures (2026-04-14)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6071`
**Canonical date**: 2026-04-14 (git blame)
**Legacy heading**

```text
Fix: SQLite ResourceWarning Test Failures (2026-04-14)
```

**Legacy heading dates**: 2026-04-14

**Commit:** `e49c1153`

### Problem

`uv run pytest` reported `17 failed, 18 errors` with the root cause being
`ResourceWarning: unclosed database in <sqlite3.Connection>`.

`filterwarnings = ["error"]` in `pyproject.toml` promotes `ResourceWarning`
to test errors. Python's cyclic GC does not guarantee `__del__` call order
within a reference cycle, so `engine.dispose()` was firing too late — or
not at all. Pytest's `unraisableexception` plugin catches these warnings via
`sys.unraisablehook` and attributes them to the *currently running* test,
not the test that created the leak, causing unrelated tests to fail.

### Root Causes

1. **`reset_datalayer()` never disposed engines.** It set
   `_shared_instance = None` / `_actor_instances = {}` but left engines
   alive. The orphaned `SqliteDataLayer` instances were eventually collected
   by cyclic GC, firing `ResourceWarning` during an unrelated test. The
   subsequent `drop_all`/`create_all` DDL calls operated on abandoned engines,
   creating a fresh connection that was immediately leaked again.

2. **Three test helpers orphaned Engine A.** The pattern:

   ```python
   dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)  # Engine A
   scoped._engine = dl._engine   # scoped now uses Engine B; Engine A abandoned
   scoped._owns_engine = False
   ```

   Engine A was never disposed. Affected files:
   `test_note_trigger.py`, `test_case.py`, `test_note.py`.

3. **Three router fixture teardowns were no-ops.** Fixtures created
   `SqliteDataLayer` instances directly (not via `get_datalayer()`), so they
   never appeared in `_actor_instances`. The teardown call
   `reset_datalayer(actor_id)` found nothing to reset, leaving the instances
   open until GC collected them.

### Fix

- **`datalayer_sqlite.py`**: Added `__enter__`/`__exit__` context manager
  to `SqliteDataLayer` (calls `self.close()` on exit). Rewrote
  `reset_datalayer()` to collect all cached instances, clear the global
  dictionaries, then call `inst.close()` on each — ensuring engines are
  disposed before references are dropped. Removed the orphan-creating
  `drop_all`/`create_all` DDL.

- **`test_note_trigger.py`**, **`test_case.py`**, **`test_note.py`**: Added
  `scoped._engine.dispose()` (or `scoped_dl._engine.dispose()`) before the
  engine swap to avoid orphaning the original engine.

- **`test_trigger_report.py`**, **`test_trigger_embargo.py`**,
  **`test_trigger_case.py`**: Changed fixture teardown to call
  `actor_dl.close()` explicitly instead of relying on `reset_datalayer()`.

### Validation

- All four linters (black, flake8, mypy, pyright) pass with zero errors.
- `uv run pytest --tb=short 2>&1 | tail -5`:
  `1402 passed, 13 skipped, 182 deselected, 5581 subtests passed`

### Lessons Learned

- `reset_datalayer()` must dispose engines *before* clearing references, not
  rely on GC. "Clear the reference, GC will clean up" is unsafe for
  resources that emit `ResourceWarning` on finalisation.
- The engine-swap pattern (`scoped._engine = new_dl._engine`) must always
  dispose the old engine first; otherwise the old engine is silently
  orphaned.
- Pytest `filterwarnings = ["error"]` + `ResourceWarning` + cyclic GC =
  test-contamination failures that appear in unrelated tests. When tests
  fail with `ResourceWarning` about unclosed resources, look for orphaned
  instances in fixture teardowns and helper functions, not in the failing
  test itself.
- `__enter__`/`__exit__` on `SqliteDataLayer` allows safe use in test
  helpers via `with SqliteDataLayer(...) as dl:`, preventing technical debt
  from per-call dispose boilerplate.
