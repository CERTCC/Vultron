---
source: ISSUE-1090
timestamp: '2026-06-22T18:10:50.000689+00:00'
title: Refactor test_receive_report_case_tree.py — extract fixtures and group by tree
  phase
type: implementation
---

## Issue #1090 — P9: Refactor test_receive_report_case_tree.py — extract fixtures and group by tree phase

Refactored `test/core/behaviors/case/test_receive_report_case_tree.py`
(917 lines, 21 flat test functions) by extracting shared fixtures to
`conftest.py` and grouping the flat test functions into 5 classes by tree
phase.

**Changes**:

- Moved 10 fixtures (`datalayer`, `actor_id`, `reporter_actor_id`, `actor`,
  `reporter_actor`, `report`, `reporter_accepted_status`,
  `vendor_received_status`, `offer`, `bridge`) to
  `test/core/behaviors/case/conftest.py` for sharing with sibling tree test
  files
- Grouped 21 flat test functions into `TestTreeStructure` (4),
  `TestTreeFlow` (4), `TestTreeIdempotency` (2), `TestParticipantCreation`
  (4), `TestEmbargoInitialization` (7)
- Moved module-level imports (`CVDRole`, `EM`, `PEC`, etc.) out of individual
  test bodies

All 21 tests pass. No logic changes. 3469 unit tests pass overall.

PR: <https://github.com/CERTCC/Vultron/pull/1103>
