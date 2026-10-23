---
source: CONCERN-3977
timestamp: '2026-10-05T19:02:52.691799+00:00'
title: A duplicate CaseProposal is the same proposal id, not the same report (CP-05-006)
type: learning
---

## Original concern

CP-05-006 said a duplicate `Create(as_CaseProposal)` for a report already accepted MUST get the stored `Accept` re-sent unchanged, with its original identifier (ADR-0080).
The receiving tree's guards are proposal-keyed on purpose: a report-keyed guard is one a sender can satisfy to skip the admission gate.
So the spec and the tree disagreed on what counts as a duplicate, and a same-report, different-id proposal was treated as a fresh admission and got a new `Accept` (new id) and a second `Create(VulnerabilityCase)`.

## Decision

The unit of idempotency is the proposal id.

- CP-05-006 now keys the duplicate on the proposal id. The stored `Accept` is re-sent for a redelivery of the same proposal; that implementation is tracked by #2890.
- New CP-05-008: a new proposal id naming an accepted report is a new request. It is admitted and answered with its own `Accept`. The existing case is reused only when the proposer owns it; any other proposer gets a separate case (CBT-06-002).
- Today `LoadExistingCaseNode` looks up the case by the sender-chosen report id alone, so a second proposer joins the first proposer's case. A strict-xfail test pins CP-05-008 until #4221 keys the reuse on the proposer.
- Suggested lookup for the stored `Accept`: carry its id and the case id on `CaseProposalAdmissionRecord`, as `CaseProposalDeclineRecord.reject_activity_id` does for the `Reject`.
- No ADR: ADR-0080 already treats a duplicate as the same request.

**Resolved**: 2026-10-05 — implementation tracked in #4221 (proposer-keyed reuse) and #2890 (stored-`Accept` re-send).
Docs PR: <https://github.com/CERTCC/Vultron/pull/4220>.
Spec: `specs/case-proposal.yaml`.
Notes: `notes/case-proposal.md`.
