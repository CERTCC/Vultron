---
source: NOTES-demo-future-ideas--pre-case-ack-flow
timestamp: '2026-10-12T23:51:08.064505+00:00'
title: 'Demo future ideas: pre-case ACK flow (stale plan, no tracking issue)'
type: note
---

Archived from `notes/demo-future-ideas.md` by #4497 (notes sweep). Stale: the plan
for #1221 (Task #2050) explicitly does not use `auto_create_case=False`, so no planned demo
exercises the pre-case ACK path, and the cited test docstring no longer mentions #1133.
The flag itself shipped (#1272; `vultron/core/use_cases/received/report.py`). The demo
idea is carried on epic #1160.

---

## Pre-case ACK flow (`auto_create_case=False`)

Issue #1133 introduced `ActorConfig.auto_create_case` (default: `True`). When
`False`, the receiver stores the inbound report but does **not** auto-create a
`VulnerabilityCase`, enabling the receiver to send a pre-case
`Read(Offer(Report))` acknowledgment (`AckReportReceivedUseCase`) before
deciding to accept or reject.

The **tentative rejection → acceptance** scenario (#1221) is the first planned
demo to exercise this path:

1. Finder submits report.
2. Vendor (with `auto_create_case=False`) sends pre-case ACK via trigger.
3. Vendor invalidates report (RM:R→I) — "tentative rejection".
4. Vendor later validates (RM:I→V) and engages — "reconsideration".

Once #1221 is implemented, `ack_report` should be wired into the per-scenario
`_*_EXPECTED_EVENT_TYPES` tuples under `test/ci/invariants/` (e.g.
`_FV_EXPECTED_EVENT_TYPES` in `test/ci/invariants/test_fv_invariants.py`,
currently excluded; see the `test_invariant_5_expected_event_types_present`
docstring citing #1133).
