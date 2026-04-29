---
title: "D5-7-EMSTATE-1 \u2014 Embargo initialization must update CaseStatus\
  \ EM state"
type: implementation
date: '2026-04-10'
source: D5-7-EMSTATE-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 5485
legacy_heading: "D5-7-EMSTATE-1 \u2014 Embargo initialization must update\
  \ CaseStatus EM state"
date_source: git-blame
---

## D5-7-EMSTATE-1 — Embargo initialization must update CaseStatus EM state

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:5485`
**Canonical date**: 2026-04-10 (git blame)
**Legacy heading**

```text
D5-7-EMSTATE-1 — Embargo initialization must update CaseStatus EM state
```

**Completed**: Priority 320

**Problem**: After `InitializeDefaultEmbargoNode` created and attached a
default embargo to a case, `CaseStatus.em_state` remained `EM.NONE`. The
embargo was created and stored as `active_embargo` but the state machine
position was never updated.

**Fix**:

- `vultron/core/behaviors/case/nodes.py`: Added `EM` import; in
  `InitializeDefaultEmbargoNode.update()`, after attaching the embargo,
  now sets `stored_case.current_status.em_state = EM.PROPOSED` and calls
  `stored_case.record_event(embargo.id_, "embargo_initialized")`.
- `vultron/demo/two_actor_demo.py`: Updated final-state assertion from
  `EM.NO_EMBARGO` to `EM.PROPOSED`; the demo creates a default embargo but
  does not negotiate it away, so `PROPOSED` is the correct final state.
- `test/core/behaviors/case/test_receive_report_case_tree.py`: Added 3 new
  tests verifying the EM state update, event recording, and idempotency guard.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1412 passed, 10 skipped, 5581 subtests passed in 70.18s`
