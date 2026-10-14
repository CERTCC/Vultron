---
source: NOTES-case-ledger-authority--the-bootstrap-window-this-replaced
timestamp: '2026-10-12T19:32:52.093196+00:00'
title: The bootstrap window this replaced
type: note
---

**Archived:** 2026-10-12
**Reason:** history of retired authority signals; the rule (authority is the CASE_MANAGER role) stays in the parent section
**Superseded by:** CM-02-012, test_case_manager_role_takes_authority_arm_without_service_object

---

## The bootstrap window this replaced

The retired signals were not merely redundant, they were wrong in a reachable
state. Under ADR-0041 the CaseActor `Service` object is written *before* the
case exists, so it carries no `context` — and a `context == case_id` scan
therefore found nothing. In that window the real authority **failed its own
hosting test** and took the *participant* arm of the announce split on its own
ledger, validating a hash chain it owns. Role membership is stable from
replica-seed onward (CP-09-004) and has no such window; the regression test is
`test_case_manager_role_takes_authority_arm_without_service_object`
(CM-02-012).

A related trap lived in the deleted `_find_case_actor` helper: on a miss it
returned *the first arbitrary `Service` in the store*, so a failed lookup was
indistinguishable from a successful one and published a plausible-looking
address belonging to some other case. When a resolver cannot answer, it must
say so.
