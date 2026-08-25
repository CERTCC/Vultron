---
title: Exchange demos must discover the canonical case from the DataLayer after validate-report
type: learning
timestamp: '2026-08-17T00:00:00+00:00'
source: ISSUE-1994
signal: design-question
---

## Decision

`setup_case_precondition` in exchange demos must NOT use `create_case_activity`
to create a local vendor-owned case. Instead, it should:

1. Submit and validate the report.
2. Call `_find_canonical_case(client)` — `GET /datalayer/VulnerabilityCases/`
   returns a `dict[str, dict]` keyed by object ID; pick the first entry with
   non-empty `case_participants`.

## Why

When the validate-report BT processes `rm_validate_report_activity`,
`ProposeReportCaseToActorNode` fires automatically and delivers a
`Create(CaseProposal)` to the CaseActor. The CaseActor creates the **canonical**
`VulnerabilityCase` (ADR-0041) and adds vendor (CASE_OWNER), reporter, and
CaseActor (CASE_MANAGER) as initial participants via `_AddVendorOwnerParticipantNode`
and `_AddReporterParticipantNode`.

A separate `create_case_activity` POST creates a **second**, vendor-local case
that:

- Has no `ReportCaseLink`, so `create_case_received` skips it ("no
  ReportCaseLink and sender is not the CaseActor").
- Gets `participants=0` because the BT sequence fails when
  `ProposeCaseToActorNode` finds no linked report (CP-01-004).
- Is a completely different object from the canonical case the CaseActor owns.

## Implication for other exchange demos

Any exchange demo that calls `create_case_activity` directly may be tracking
the wrong case ID. The CaseActor's canonical case is always discoverable from
the shared DataLayer after validate-report via
`GET /datalayer/VulnerabilityCases/`.

## Related

- #2356 — `run_exchange_demos` does not call `assert_demo_success`; the
  validate-report flow already contains `demo_check` failures in at least two
  other exchange demos.
- TestClientRouter does not register `https://vultron.example`, so the
  CaseActor's `Create(VulnerabilityCase)` delivery to vendor is silently dropped
  in the single-backend exchange demo test environment. The canonical case IS in
  the DataLayer even though vendor never receives it in their inbox.

**Promoted**: 2026-08-24 — captured in vultron/demo/AGENTS.md + notes/case-proposal.md.
Docs PR: [PR URL TBD].
