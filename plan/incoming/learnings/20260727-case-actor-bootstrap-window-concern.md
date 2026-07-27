---
title: "CASE_MANAGER participant bootstrap window creates transient routing dependency"
type: learning
timestamp: 2026-07-27
source: ISSUE-1733
signal: concern
---

After #1733, the vendor's case has no CASE_MANAGER CaseParticipant record until
`Create(VulnerabilityCase)` is received from the case-actor and bootstrap
completes. During this window, `_resolve_case_manager_id` returns `None` and
the fallback to `_find_case_actor_id` (via `VultronReportCaseLink.trusted_case_actor_id`)
is the only routing path for report activities.

**Risk**: If `trusted_case_actor_id` is also absent (e.g., `Accept(CaseProposal)`
was not yet processed by the vendor when a `validate_report` trigger fires),
`_compute_report_addressees` returns `None` and the activity is silently dropped.

**Fragility**: This is a timing/ordering dependency between the CaseProposal
protocol and report-phase triggers. It is likely benign in practice (report
triggers come after case creation which comes after Accept), but is worth
tracking as a potential source of lost activities in edge cases or race conditions.

**Suggested follow-up**: Add a spec entry (CP or CLP) that explicitly orders
report-phase trigger emission after `Accept(CaseProposal)` is confirmed received,
or add a guard in `EmitValidateReportActivity` that fails with a retryable error
when no case-actor ID is resolvable.
