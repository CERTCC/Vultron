---
title: "QUALITY-1 \u2014 Treat pytest warnings as errors (2026-03-26)"
type: implementation
timestamp: '2026-03-26T00:00:00+00:00'
source: QUALITY-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3413
legacy_heading: "QUALITY-1 \u2014 Treat pytest warnings as errors (2026-03-26)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-26'
---

## QUALITY-1 — Treat pytest warnings as errors (2026-03-26)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3413`
**Canonical date**: 2026-03-26 (git blame)
**Legacy heading**

```text
QUALITY-1 — Treat pytest warnings as errors (2026-03-26)
```

**Legacy heading dates**: 2026-03-26

**Task**: Configure pytest to treat warnings as errors, fix any existing
warnings surfaced by this change.

**What was done**:

- Added `filterwarnings = ["error"]` to `[tool.pytest.ini_options]` in
  `pyproject.toml` (per `specs/tech-stack.yaml` IMPLTS-07-006).
- Fixed `ResourceWarning: unclosed file 'mydb.json'` in
  `vultron/adapters/driven/datalayer_tinydb.py`:
  - Added `TinyDbDataLayer.close()` method that calls `self._db.close()` to
    explicitly release TinyDB file handles.
  - Updated `reset_datalayer()` to call `.close()` on each instance before
    dropping references, preventing unclosed file warnings when instances are
    garbage-collected.
- Updated `.github/skills/run-tests/SKILL.md` to document the warnings-as-errors
  behaviour and the requirement not to suppress warnings without fixing root causes.
- Recorded two pre-existing bugs in `plan/BUGS.md`:
  - BUG-2026032602: `uv run` fails due to `snapshot/Q1-2026` git tag (workaround:
    use `.venv/bin/pytest` directly).
  - BUG-2026032603: Test ordering dependency in `test_datalayer_isolation.py`
    (passes in full suite; fails when run in isolation due to vocabulary registry
    not being populated).

**Validation**:

- `.venv/bin/black vultron/ test/ && .venv/bin/flake8 vultron/ test/`
- `.venv/bin/pytest --tb=short 2>&1 | tail -5` → `1026 passed, 5581 subtests passed`
