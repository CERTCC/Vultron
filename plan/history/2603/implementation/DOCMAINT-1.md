---
title: "DOCMAINT-1 \u2014 Update outdated notes/ files"
type: implementation
timestamp: '2026-03-30T00:00:00+00:00'
source: DOCMAINT-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3596
legacy_heading: "DOCMAINT-1 \u2014 Update outdated notes/ files (COMPLETE\
  \ 2026-03-30)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-30'
---

## DOCMAINT-1 — Update outdated notes/ files

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3596`
**Canonical date**: 2026-03-30 (git blame)
**Legacy heading**

```text
DOCMAINT-1 — Update outdated notes/ files (COMPLETE 2026-03-30)
```

**Legacy heading dates**: 2026-03-30

**Task:** DOCMAINT-1 (PRIORITY-250 pre-300 cleanup)

**What was done:**

Updated four notes files to replace outdated forward-looking language with
current implementation status:

- **`notes/activitystreams-semantics.md`** (~line 333): Updated "CaseActor
  broadcast is not yet implemented" to reflect implementation in
  `UpdateCaseReceivedUseCase._broadcast_case_update()` (completed in
  PRIORITY-200 CA-2, 2026-03-25).

- **`notes/state-machine-findings.md`** (Section 9 "Completion Status"):
  Removed the warning about fictional commit SHAs and the table of fictional
  commit hashes. Replaced with an accurate per-item status table referencing
  actual implementation phases (P90-1–P90-5, TECHDEBT-32b, TECHDEBT-39).
  Updated "Deferred (explicit)" section: OPP-05 is now done (TECHDEBT-39,
  2026-03-24), full STATUS dict deprecation is done (P90-1/P90-4); only
  OPP-06 (VFD/PXA machines) remains deferred.

- **`notes/datalayer-refactor.md`** (TECHDEBT-32b/32c sections): Marked
  TECHDEBT-32b as completed (2026-03-24) with a summary of what was done;
  marked TECHDEBT-32c as pending with a clearer label.

- **`notes/codebase-structure.md`** (multiple sections):
  - Updated "Top-Level Module Reorganization Status": removed stale references
    to `vultron/api/v2/backend/handler_map.py`, `vultron/dispatcher_errors.py`,
    `vultron/behavior_dispatcher.py`, and `vultron/enums.py` (all removed/
    relocated); added their canonical current locations.
  - "API Layer Architecture": Renamed from "Future Refactoring" to
    "Historical (Completed in VCR Batch B / P65)"; replaced old path table
    with current canonical locations.
  - "Handlers Module Structure": Renamed to "Use-Case Module Structure
    (Completed — REORG-1)"; updated to describe current
    `vultron/core/use_cases/` layout.
  - TECHDEBT-11: Updated to note that new test directories exist but old ones
    have not been removed yet.
  - TECHDEBT-12: Marked resolved (trigger_services removed in VCR Batch D).
  - "Known Gap: Outbox Delivery Not Implemented": Replaced with "Resolved:
    Outbox Delivery (OX-1.0–1.4)".
  - "Resolved: app.py Root Logger Side Effect": Updated path from
    `vultron/api/v2/app.py` to `vultron/adapters/driving/fastapi/app.py`.
  - "Trigger Services Package": Replaced forward-looking migration plan with
    completed-status summary showing current canonical locations.
  - Fixed Object IDs section: `vultron/as_vocab/base/utils.py` →
    `vultron/wire/as2/vocab/base/utils.py`; `vultron/api/v2/routers/datalayer.py`
    → `vultron/adapters/driving/fastapi/routers/datalayer.py`.

**Tests:** 1080 passed, 5581 subtests passed (no code changes; docs only).
