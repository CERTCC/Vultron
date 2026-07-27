---
title: "_compute_report_addressees falls back to _find_case_actor_id in multi-container topology"
type: learning
timestamp: 2026-07-27
source: ISSUE-1733
signal: design-question
---

When implementing #1733, `_compute_report_addressees` in
`vultron/core/behaviors/report/nodes/emit.py` was extended to fall back to
`_find_case_actor_id(dl, case.id_)` when `_resolve_case_manager_id` returns
`None`.

**Why**: After AC-2 (vendor BT no longer creates local CaseParticipant records),
the vendor's case has no CASE_MANAGER participant until it receives
`Create(VulnerabilityCase)` from the case-actor and completes bootstrap. During
that window, `_resolve_case_manager_id` returns `None` and report activities
would have no routable recipients. The fallback routes via
`VultronReportCaseLink.trusted_case_actor_id` (set when vendor receives
`Accept(CaseProposal)`), which is available earlier.

**Interpretation**: routing to the known case-actor ID is correct here — the
case-actor is the authoritative CASE_MANAGER in the multi-container topology
regardless of whether its participant record is in the vendor's local DataLayer.
