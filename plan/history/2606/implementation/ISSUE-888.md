---
source: ISSUE-888
timestamp: '2026-06-18T16:26:42.726081+00:00'
title: Remove events/record_event from wire-layer VulnerabilityCase
type: implementation
---

## Issue #888 — Remove events field and record_event() from wire-layer VulnerabilityCase

Removed the duplicate `events: list[CaseEvent]` field and `record_event()`
method from the wire-layer `VulnerabilityCase`
(`vultron/wire/as2/vocab/objects/vulnerability_case.py`). The core model
(`vultron/core/models/case.py`) remains the authoritative source.

Also deleted the `case_event.py` compat shim
(`vultron/wire/as2/vocab/objects/case_event.py`) which had no remaining
callers after this change.

Key fix discovered during implementation: `is_case_model()` in
`vultron/core/models/protocols.py` used `hasattr(obj, "record_event")` as a
structural discriminator. Removing the method broke this type guard, causing
`find_case_by_report_id()` and 440 other tests to fail. Fixed by replacing
the check with `hasattr(obj, "case_statuses")`, which is a declared `CaseModel`
Protocol member present on all implementations.

PR: <https://github.com/CERTCC/Vultron/pull/1041>
