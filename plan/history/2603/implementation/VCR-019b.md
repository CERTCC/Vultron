---
title: "VCR-019b \u2014 Move RM, EM, CVDRoles enums to `vultron/core/states/`\
  \ (2026-03-19)"
type: implementation
timestamp: '2026-03-18T00:00:00+00:00'
source: VCR-019b
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2180
legacy_heading: "VCR-019b \u2014 Move RM, EM, CVDRoles enums to `vultron/core/states/`\
  \ (2026-03-19)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-19'
---

## VCR-019b — Move RM, EM, CVDRoles enums to `vultron/core/states/` (2026-03-19)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2180`
**Canonical date**: 2026-03-18 (git blame)
**Legacy heading**

```text
VCR-019b — Move RM, EM, CVDRoles enums to `vultron/core/states/` (2026-03-19)
```

**Legacy heading dates**: 2026-03-19

Moved three enum modules from `vultron/bt/` subpackages into
`vultron/core/states/`:

- `vultron/bt/report_management/states.py` → `vultron/core/states/rm.py`
  (exports `RM`, `RM_CLOSABLE`, `RM_UNCLOSED`, `RM_ACTIVE`)
- `vultron/bt/embargo_management/states.py` → `vultron/core/states/em.py`
  (exports `EM`)
- `vultron/bt/roles/states.py` → `vultron/core/states/roles.py`
  (exports `CVDRoles`, `add_role`)

Updated `vultron/core/states/__init__.py` to re-export all new symbols
alongside the existing CS exports. Updated all 59 callers across `vultron/`,
`test/`, and `integration_tests/` with `sed` bulk replacement. Deleted the
original source files with no shims.

`MessageTypes`, `CapabilityFlag`, and `ActorState` remain in `vultron/bt/`
per the VCR-019c study (Group D — BT-runtime-only, no callers in core).

### Test results

982 passed, 5581 subtests (unchanged from baseline).
