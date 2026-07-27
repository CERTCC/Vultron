---
source: ISSUE-1733
timestamp: '2026-07-27T22:34:22.023939+00:00'
title: 'fix(case-actor): VultronCaseActor/VultronParticipant created on case-actor
  container'
type: implementation
---

## Issue #1733 — fix(case-actor): VultronCaseActor and VultronParticipant created on case-actor container

Implemented all 6 acceptance criteria. VultronCaseActor (Service) and VultronParticipant (CaseParticipant) records are now created on the dedicated case-actor container when it processes Create(as_CaseProposal), not on vendor/coordinator containers. CreateCaseActorNode simplified to URL-resolution only. Docker Compose wiring corrected. Two cascade fixes applied: SendOfferCaseManagerRoleNode uses stub participant when record absent;_compute_report_addressees falls back to _find_case_actor_id when no CASE_MANAGER participant bootstrapped yet. Demo verification updated to assert case-actor container holds records. 5475 tests passing.

PR: <https://github.com/CERTCC/Vultron/pull/1748>
