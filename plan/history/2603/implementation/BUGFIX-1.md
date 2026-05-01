---
title: "BUGFIX-1 \u2014 Pytest Logging Noise"
type: implementation
timestamp: '2026-03-09T00:00:00+00:00'
source: BUGFIX-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 197
legacy_heading: "Phase BUGFIX-1 \u2014 Pytest Logging Noise (COMPLETE 2026-02-27)"
date_source: git-blame
legacy_heading_dates:
- '2026-02-27'
---

## BUGFIX-1 — Pytest Logging Noise

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:197`
**Canonical date**: 2026-03-09 (git blame)
**Legacy heading**

```text
Phase BUGFIX-1 — Pytest Logging Noise (COMPLETE 2026-02-27)
```

**Legacy heading dates**: 2026-02-27

- Root-logger side effect in `app.py` fixed (BUGFIX-1.1)
- Spurious `print()` calls replaced in four test files (BUGFIX-1.2)
- Test output clean under `uv run pytest`
