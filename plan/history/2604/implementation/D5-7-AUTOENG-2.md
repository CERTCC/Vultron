---
title: "D5-7-AUTOENG-2 \u2014 Auto-cascade validate \u2192 engage (2026-04-14)"
type: implementation
date: '2026-04-10'
source: D5-7-AUTOENG-2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 5515
legacy_heading: "D5-7-AUTOENG-2 \u2014 Auto-cascade validate \u2192 engage\
  \ (2026-04-14)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-14'
---

## D5-7-AUTOENG-2 — Auto-cascade validate → engage (2026-04-14)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:5515`
**Canonical date**: 2026-04-10 (git blame)
**Legacy heading**

```text
D5-7-AUTOENG-2 — Auto-cascade validate → engage (2026-04-14)
```

**Legacy heading dates**: 2026-04-14

**Task**: After a successful `validate-report` trigger, automatically invoke
`engage-case` so demos and integrations no longer need a separate manual step.

**Changes**:

- `vultron/core/use_cases/received/case.py`: Added `_auto_engage()` helper to
  `ValidateCaseUseCase`; called on BT `SUCCESS` (received-message path).
- `vultron/core/use_cases/triggers/report.py`: Added `_auto_engage()` helper to
  `SvcValidateReportUseCase`; called on BT `SUCCESS` (trigger path). Captures
  `bridge.execute_with_setup()` result.
- `vultron/demo/two_actor_demo.py`: Removed manual `engage-case` trigger step
  (step 5 now describes the auto-cascade, not a separate call).
- `test/core/use_cases/received/test_report.py`: Updated descriptions;
  added `test_full_flow_vendor_auto_engages_after_validate`.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1413 passed, 10 skipped, 5581 subtests passed in 84.37s`
