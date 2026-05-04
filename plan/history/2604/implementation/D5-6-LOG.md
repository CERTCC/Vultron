---
title: "D5-6-LOG \u2014 Improve process-flow logging across demo containers"
type: implementation
timestamp: '2026-04-06T00:00:00+00:00'
source: D5-6-LOG
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 4525
legacy_heading: "D5-6-LOG \u2014 Improve process-flow logging across demo\
  \ containers"
date_source: git-blame
---

## D5-6-LOG — Improve process-flow logging across demo containers

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:4525`
**Canonical date**: 2026-04-06 (git blame)
**Legacy heading**

```text
D5-6-LOG — Improve process-flow logging across demo containers
```

**Task**: PRIORITY-310, D5-6-LOG

### Root cause fixed

`py_trees.behaviour.Behaviour.__init__` sets `self.logger = logging.Logger(name)`
where `logging` is `py_trees.logging` (a custom module, not stdlib). The custom
`py_trees.logging.Logger` class has `parent=None` and a single-arg `info(msg)`
— all BT node `self.logger.info/debug/error(...)` calls were silently dropped.

**Fix**: Override `self.logger` in `DataLayerCondition.__init__` and
`DataLayerAction.__init__` (in `vultron/core/behaviors/helpers.py`) with
`logging.getLogger(f"{__name__}.{self.__class__.__name__}")` after
`super().__init__()`.

### Changes

1. **`vultron/core/behaviors/helpers.py`**: Added
   `logger: logging.Logger  # type: ignore[assignment]` class attribute and
   `self.logger = logging.getLogger(...)  # type: ignore[assignment]` in both
   `DataLayerCondition.__init__` and `DataLayerAction.__init__`.

2. **`vultron/core/behaviors/report/nodes.py`**: Improved log messages in
   `TransitionRMtoValid` and `TransitionRMtoInvalid` to include report name
   and actor ID (e.g., `"RM → VALID for report '%s' (actor '%s')"`).

3. **`vultron/core/behaviors/case/nodes.py`**: Improved
   `CreateInitialVendorParticipant.update()` to log roles and `rm_state`
   explicitly. Fixed generator to use `str(r.value)` instead of `r.value`.

4. **`vultron/adapters/driving/fastapi/routers/actors.py`**: Changed the
   "Parsing activity from request body" log to multiline indented JSON
   (`json.dumps(body, indent=2, default=str)`).

5. **`vultron/core/use_cases/triggers/requests.py`**: Added
   `SubmitReportTriggerRequest` with `report_name`, `report_content`,
   `recipient_id` fields.

6. **`vultron/core/use_cases/triggers/report.py`**: Added
   `SvcSubmitReportUseCase` that creates a `VulnerabilityReport` and
   `RmSubmitReportActivity` (offer), stores both in the DataLayer, and queues
   the offer in the actor's outbox.

7. **`vultron/adapters/driving/fastapi/trigger_models.py`**: Added
   `SubmitReportRequest` HTTP request body model.

8. **`vultron/adapters/driving/fastapi/_trigger_adapter.py`**: Added
   `submit_report_trigger` adapter function.

9. **`vultron/adapters/driving/fastapi/routers/trigger_report.py`**: Added
   `POST /actors/{id}/trigger/submit-report` endpoint.

10. **`vultron/demo/two_actor_demo.py`**: Updated `finder_submits_report()` to
    accept optional `finder_client`; uses the new submit-report trigger when
    provided; skips inbox delivery when finder and vendor share the same
    DataLayer (single-container tests).

11. **`test/core/behaviors/test_helpers.py`**: Added 4 tests verifying the
    logger override (uses stdlib Logger, has a parent, name includes class,
    emits records via `caplog`).

12. **`test/adapters/driving/fastapi/routers/test_trigger_report.py`**: Added
    5 tests for the submit-report endpoint (202 response, DataLayer storage,
    outbox entry, 422 for missing fields, log emission via `caplog`).

### Validation

`uv run pytest --tb=short 2>&1 | tail -5` → 1220 passed, 5581 subtests;
black/flake8/mypy/pyright all clean.
