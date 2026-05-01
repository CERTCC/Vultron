---
title: "TECHDEBT-24 (remaining) \u2014 Remove wire-layer import from `core/use_cases/case.py`"
type: implementation
timestamp: '2026-03-16T00:00:00+00:00'
source: TECHDEBT-24
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1677
legacy_heading: "TECHDEBT-24 (remaining) \u2014 Remove wire-layer import from\
  \ `core/use_cases/case.py`"
date_source: git-blame
---

## TECHDEBT-24 (remaining) — Remove wire-layer import from `core/use_cases/case.py`

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1677`
**Canonical date**: 2026-03-16 (git blame)
**Legacy heading**

```text
TECHDEBT-24 (remaining) — Remove wire-layer import from `core/use_cases/case.py`
```

**Date**: 2026-03-16
**Task**: Remove lazy `VulnerabilityCase` import from `CreateCaseReceivedUseCase.execute`

**What was done**:

- In `vultron/core/models/case.py`: changed `VultronCase.case_statuses`
  `default_factory` from `list` (empty) to `lambda: [VultronCaseStatus()]`,
  giving the domain model the same initial case status as
  `VulnerabilityCase.init_case_status()`. This ensures that when a `VultronCase`
  is stored in TinyDB and subsequently read back as a `VulnerabilityCase`, the
  `case_statuses` list is non-empty and `VulnerabilityCase.current_status`
  (`max()`) does not raise `ValueError`.
- In `vultron/core/use_cases/case.py`: removed the lazy `from vultron.wire…
  import VulnerabilityCase` and the intermediate `case_wire = VulnerabilityCase(…)`
  construction from `CreateCaseReceivedUseCase.execute`. The `VultronCase`
  already present on `request.case` is now passed directly to
  `create_create_case_tree`. `case.py` has no imports from `vultron.wire.*`.

**Lessons learned**: Enriching the domain model (option a) is architecturally
preferable to guarding symptoms in the wire type. The domain object should
always initialise to a valid state.

**Test results:** 893 passed, 0 failed (unchanged from baseline).
