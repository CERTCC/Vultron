---
title: "AF.2 — Create factories/report.py with 6 report factory functions"
type: implementation
date: 2026-04-30
source: TASK-AF-2
---

## TASK-AF AF.2 — Report Activity Factory Functions

Implemented `vultron/wire/as2/factories/report.py` with 6 factory functions
covering all report-management activities. Updated
`vultron/wire/as2/factories/__init__.py` to re-export all 6 functions and
added 27 unit tests in `test/wire/as2/factories/test_report_factories.py`.

**Factory functions created:**

- `rm_create_report_activity(report, **kwargs) -> as_Create`
- `rm_submit_report_activity(report, to, **kwargs) -> as_Offer`
- `rm_read_report_activity(report, **kwargs) -> as_Read`
- `rm_validate_report_activity(offer, **kwargs) -> as_Accept`
- `rm_invalidate_report_activity(offer, **kwargs) -> as_TentativeReject`
- `rm_close_report_activity(offer, **kwargs) -> as_Reject`

Each function wraps `pydantic.ValidationError` in
`VultronActivityConstructionError`. The validate/invalidate/close functions
use `cast(RmSubmitReportActivity, offer)` internally to satisfy mypy while
keeping the public signature as `as_Offer`. All linters (Black, flake8, mypy,
pyright) and 2041 tests pass.
