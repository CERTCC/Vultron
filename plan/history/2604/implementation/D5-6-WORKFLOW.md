---
title: "D5-6-WORKFLOW \u2014 Automate complete case creation from validate-report"
type: implementation
timestamp: '2026-04-06T00:00:00+00:00'
source: D5-6-WORKFLOW
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 4661
legacy_heading: "D5-6-WORKFLOW \u2014 Automate complete case creation from\
  \ validate-report"
date_source: git-blame
---

## D5-6-WORKFLOW — Automate complete case creation from validate-report

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:4661`
**Canonical date**: 2026-04-06 (git blame)
**Legacy heading**

```text
D5-6-WORKFLOW — Automate complete case creation from validate-report
```

**Date**: 2026-04-06
**Task**: PRIORITY-310 D5-6-WORKFLOW

### Changes

- `vultron/core/behaviors/case/nodes.py`:
  - Added `InitializeDefaultEmbargoNode`: creates a default embargo event
    (duration from actor's EmbargoPolicy, falling back to 90 days) and
    attaches it to the newly created case.
  - Added `CreateFinderParticipantNode`: reads the Offer to find the finder's
    actor ID, reuses the report-phase RM.ACCEPTED status, creates a
    `VultronParticipant` with FINDER+REPORTER roles, attaches it to the case,
    records a `"participant_added"` case event, and emits an Add notification.
  - Updated `CreateInitialVendorParticipant`: added `advance_to_accepted`
    parameter (default `False`); when `True`, advances vendor RM VALID →
    ACCEPTED immediately after participant creation (validate-report tree sets
    this; create-case tree leaves it `False` per ADR-0013).
  - Fixed `CreateCaseActivity`: replaced `dl.read(offer_id)` with
    `dl.by_type("Offer").get(offer_id)` because `VultronOffer` is not
    registered in the AS2 vocabulary and cannot be reconstructed by `read()`.

- `vultron/core/behaviors/report/validate_tree.py`:
  - Expanded `ValidationActions` sequence from 5 to 7 nodes: added
    `InitializeDefaultEmbargoNode` (after `CreateCaseNode`) and
    `CreateFinderParticipantNode` (after `CreateInitialVendorParticipant`).
  - Passes `advance_to_accepted=True` to `CreateInitialVendorParticipant`.

- `vultron/demo/two_actor_demo.py`:
  - Removed `vendor_engages_case()` function (now handled by BT).
  - Removed `vendor_adds_finder_as_participant()` function (now handled by BT).
  - Updated `run_two_actor_demo()`: removed steps 3-engage and 4-add-finder;
    added `wait_for_case_participants` right after validate-report; renumbered
    steps 5→4, 6→5; updated docstring.
  - Removed unused imports (`AddParticipantToCaseActivity`,
    `CreateParticipantActivity`, `FinderReporterParticipant`).

- `test/core/behaviors/report/test_validate_tree.py`:
  - Added `finder_actor_id` and `finder_actor` fixtures; updated `offer`
    fixture to use finder as actor.
  - Updated node count assert 5→7; updated vendor RM check VALID→ACCEPTED.
  - Added 3 new tests: finder participant created, default embargo initialized,
    vendor RM advanced to ACCEPTED.

- `test/demo/test_two_actor_demo.py`:
  - Removed `TestVendorEngagesCase` and `TestVendorAddsFinder` test classes.
  - Updated `_setup_case_with_two_participants` to remove the old manual
    engage/add-finder calls; now relies on BT + `wait_for_case_participants`.

- `test/core/behaviors/test_performance.py`:
  - Added `by_type` and `record_outbox_item` mocks to `mock_datalayer`
    fixture.

### Validation

`uv run pytest --tb=short 2>&1 | tail -5` → 1237 passed, 5581 subtests;
black/flake8/mypy/pyright all clean.
