---
title: "REORG-1 \u2014 Reorganize `vultron/core/use_cases/`"
type: implementation
date: '2026-03-30'
source: REORG-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3532
legacy_heading: "REORG-1 \u2014 Reorganize `vultron/core/use_cases/` (COMPLETE\
  \ 2026-03-30)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-30'
---

## REORG-1 — Reorganize `vultron/core/use_cases/`

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3532`
**Canonical date**: 2026-03-30 (git blame)
**Legacy heading**

```text
REORG-1 — Reorganize `vultron/core/use_cases/` (COMPLETE 2026-03-30)
```

**Legacy heading dates**: 2026-03-30

Reorganized `vultron/core/use_cases/` into clearer sub-packages per
`specs/use-case-organization.yaml` UCORG-01-001 through UCORG-04-001.

**Source moves (via `git mv`):**

- 8 received-handler modules (`actor.py`, `case.py`, `case_participant.py`,
  `embargo.py`, `note.py`, `report.py`, `status.py`, `unknown.py`) moved to
  `vultron/core/use_cases/received/`
- `action_rules.py` moved to `vultron/core/use_cases/query/`
- `_helpers.py` retained at root (shared by `received/` and `triggers/`)

**Test moves (via `git mv`):**

- 8 received test files moved to `test/core/use_cases/received/` and renamed
  to drop the `_use_cases` suffix
- `test_action_rules.py` moved to `test/core/use_cases/query/`

**Import updates:**

- `use_case_map.py` — all 8 imports updated to `received.*`; stale
  `SEMANTICS_HANDLERS` alias and `api/v2` docstring comment removed
- `vultron/adapters/driving/fastapi/routers/actors.py` — `action_rules` import
  updated to `query.action_rules`
- All moved test files — imports updated to new paths
- `test/core/use_cases/test_reporting_workflow.py` and
  `test/core/ports/test_use_case.py` — imports updated in place

**New files:** `received/__init__.py`, `query/__init__.py`,
`test/core/use_cases/received/__init__.py`,
`test/core/use_cases/query/__init__.py`, and `vultron/core/use_cases/README.md`
documenting the trigger→received→sync information flow.

**Tests:** 1027 passed, 5581 subtests (unchanged from before).

**Commit:** 3337e7e0
