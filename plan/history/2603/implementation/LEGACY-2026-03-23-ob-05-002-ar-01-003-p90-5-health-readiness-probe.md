---
title: "OB-05-002, AR-01-003, P90-5 \u2014 Health readiness probe, operation\
  \ IDs, OPP-06 spec"
type: implementation
date: '2026-03-23'
source: LEGACY-2026-03-23-ob-05-002-ar-01-003-p90-5-health-readiness-probe
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2632
legacy_heading: "OB-05-002, AR-01-003, P90-5 \u2014 Health readiness probe,\
  \ operation IDs, OPP-06 spec"
date_source: git-blame
---

## OB-05-002, AR-01-003, P90-5 — Health readiness probe, operation IDs, OPP-06 spec

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2632`
**Canonical date**: 2026-03-23 (git blame)
**Legacy heading**

```text
OB-05-002, AR-01-003, P90-5 — Health readiness probe, operation IDs, OPP-06 spec
```

**Date**: 2026-03-23
**Commit**: 2d4308e

### What was done

Three Quick Win tasks completed in a single run:

**OB-05-002** — Implemented DataLayer connectivity check in
`/health/ready`. The `readiness()` endpoint now injects the DataLayer via
`Depends(get_datalayer)`, probes it with `dl.read("")`, and returns HTTP 503 if
the backend raises. The test file was updated to use the shared `datalayer`
fixture and a new `client_health_failing` fixture; a new test verifies the 503
path.

**AR-01-003** — Added unique, stable `operation_id` values to all 39 FastAPI
route decorators across `actors.py`, `datalayer.py`, `examples.py`,
`health.py`, `trigger_case.py`, `trigger_embargo.py`, `trigger_report.py`, and
`v2_router.py`. Convention: `{resource}_{action}` (e.g. `actors_list`,
`datalayer_get_offer`, `examples_validate_case`).

**P90-5** — Added `BT-12 VFD/PXA State Machine Usage` section with requirement
`BT-12-001` and verification criteria to `specs/behavior-tree-integration.yaml`.
Captures OPP-06: any future VFD/PXA state transitions MUST use
`create_vfd_machine()` / `create_pxa_machine()` rather than hand-rolled logic.

### Test results

977 passed, 5581 subtests (baseline was 976; +1 new test for OB-05-002 503 path).
