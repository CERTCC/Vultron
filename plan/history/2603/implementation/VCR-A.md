---
title: "VCR-A \u2014 Batch VCR-A dead code and shim removal (2026-03-18)"
type: implementation
date: '2026-03-18'
source: VCR-A
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1835
legacy_heading: "VCR-A \u2014 Batch VCR-A dead code and shim removal (2026-03-18)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-18'
---

## VCR-A — Batch VCR-A dead code and shim removal (2026-03-18)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1835`
**Canonical date**: 2026-03-18 (git blame)
**Legacy heading**

```text
VCR-A — Batch VCR-A dead code and shim removal (2026-03-18)
```

**Legacy heading dates**: 2026-03-18

**Tasks completed**: VCR-001, VCR-015a, VCR-015b, VCR-024, VCR-031, VCR-032
**Tasks skipped**: VCR-006 (depends on PREPX-2), VCR-030 (blocked — see below)

### What was done

- **VCR-001**: Deleted `vultron/adapters/driven/dns_resolver.py` (stub with no
  implementation or callers). Updated `vultron/adapters/driven/__init__.py` docstring.
- **VCR-015a**: Deleted `vultron/api/v2/data/status.py` (shim re-exporting from
  `vultron.core.models.status`). Updated 4 callers to import from the canonical
  source: `test/core/behaviors/report/test_validate_tree.py`,
  `test/core/behaviors/report/test_nodes.py`,
  `test/api/v2/routers/test_trigger_report.py`,
  `test/api/v2/backend/test_trigger_services.py`.
- **VCR-015b**: Deleted `vultron/api/v2/data/types.py` (`UniqueKeyDict` class with
  no callers outside its own file).
- **VCR-024**: Deleted `vultron/core/ports/dns_resolver.py` (Protocol stub with no
  callers).
- **VCR-031**: Deleted `vultron/behavior_dispatcher.py` (backward-compat shim).
  Updated `test/test_behavior_dispatcher.py` to import `get_dispatcher` and
  `DirectActivityDispatcher` directly from `vultron.core.dispatcher`.
- **VCR-032**: Moved `VultronApiHandlerNotFoundError` from
  `vultron/dispatcher_errors.py` into `vultron/errors.py`. Updated
  `vultron/core/dispatcher.py` and `vultron/api/v2/errors.py` to import from
  `vultron.errors`. Deleted `vultron/dispatcher_errors.py`.

### VCR-030 blocked

VCR-030 (delete `vultron/sim/`) was found to have callers in `vultron/bt/`:

- `vultron/bt/states.py`
- `vultron/bt/messaging/outbound/behaviors.py`
- `vultron/bt/messaging/inbound/fuzzer.py`
- `vultron/bt/report_management/_behaviors/report_to_others.py`

All import `vultron.sim.messages.Message`. VCR-030 is updated in the plan to
reflect the blocked status and the prerequisite work needed.

### Test results

966 passed, 5581 subtests, 5 warnings (up from 961 before this batch).
