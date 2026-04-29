---
title: "TECHDEBT-17, TECHDEBT-18, TECHDEBT-20 \u2014 Batch 80a: Dead code\
  \ removal (2026-03-16)"
type: implementation
date: '2026-03-16'
source: LEGACY-2026-03-16-techdebt-17-techdebt-18-techdebt-20-batch-80a-de
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1598
legacy_heading: "TECHDEBT-17, TECHDEBT-18, TECHDEBT-20 \u2014 Batch 80a: Dead\
  \ code removal (2026-03-16)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-16'
---

## TECHDEBT-17, TECHDEBT-18, TECHDEBT-20 — Batch 80a: Dead code removal (2026-03-16)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1598`
**Canonical date**: 2026-03-16 (git blame)
**Legacy heading**

```text
TECHDEBT-17, TECHDEBT-18, TECHDEBT-20 — Batch 80a: Dead code removal (2026-03-16)
```

**Legacy heading dates**: 2026-03-16

**Tasks**: TECHDEBT-17, TECHDEBT-18, TECHDEBT-20

- **TECHDEBT-17**: Deleted 279 lines of pre-refactor bare function stubs
  (`create_embargo_event`, `add_embargo_event_to_case`,
  `remove_embargo_event_from_case`, `announce_embargo_event_to_case`,
  `invite_to_embargo_on_case`, `accept_invite_to_embargo_on_case`,
  `reject_invite_to_embargo_on_case`) from `vultron/core/use_cases/embargo.py`
  that duplicated the class-based use cases above them and were not called
  anywhere (shim layer already delegated to class-based versions).
- **TECHDEBT-18**: Deleted 53 lines — a duplicate import block and second
  definition of `_resolve_offer_and_report` from
  `vultron/core/use_cases/triggers/report.py` (block starting with bare
  `import logging` after `SvcCloseReportUseCase`).
- **TECHDEBT-20**: Deleted 25 lines — a duplicate import block ending with
  `logger = logging.getLogger(__name__)` from
  `vultron/core/use_cases/triggers/embargo.py` (block after
  `SvcTerminateEmbargoUseCase`).

**Test results:** 893 passed, 0 failed (unchanged from baseline).

---

### TECHDEBT-19 + TECHDEBT-24 (partial) — Remove api.v2.* and wire-layer imports from core (2026-03-16)

**Task**: TECHDEBT-19 (Batch 80b) + partial TECHDEBT-24.

**What was done**:

- Moved `rehydrate` from `vultron/api/v2/data/rehydration.py` to
  `vultron/wire/as2/rehydration.py`. Added `dl: DataLayer | None = None`
  parameter so callers with a DataLayer in scope can pass it directly (avoiding
  the adapter-layer `get_datalayer()` fallback). Module-level import of
  `get_datalayer` enables monkeypatching in tests. Deleted the old
  `api/v2/data/rehydration.py` file entirely (no shim — see `plan/IDEAS.md`).
  Updated all callers (`inbox_handler.py`, `cli.py`, `routers/datalayer.py`,
  `triggers/report.py`, and ~25 test patches) to import from the new location.
- Updated `triggers/report.py` status imports from `vultron.api.v2.data.status`
  to `vultron.core.models.status` (the authoritative location; `api.v2.data.status`
  was already a re-export shim).
- Partial TECHDEBT-24 (`triggers/_helpers.py`): Removed `VulnerabilityCase` and
  `ParticipantStatus` imports from `triggers/_helpers.py`. Changed
  `resolve_case` return type to `CaseModel` (Protocol). Added
  `append_rm_state(rm_state, actor, context)` method to `CaseParticipant` (wire)
  and `ParticipantModel` (Protocol in `_types.py`), eliminating the need to
  instantiate `ParticipantStatus` in the helper.
- TECHDEBT-24 `case.py` deferred: Passing `VultronCase` directly to
  `create_create_case_tree` caused `VulnerabilityCase.current_status` to fail
  with `max() iterable argument is empty` after a TinyDB round-trip because
  `VultronCase` initialises `case_statuses = []` while `VulnerabilityCase` uses
  `default_factory=init_case_status` to produce `[CaseStatus()]`. The lazy
  `VulnerabilityCase` import in `case.py` was retained; see TECHDEBT-24
  remaining item in the plan for the options.

**Test results:** 893 passed, 0 failed (unchanged from baseline).
