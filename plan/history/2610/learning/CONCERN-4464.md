---
source: CONCERN-4464
timestamp: '2026-10-12T14:30:03.967613+00:00'
title: A new CaseProposal for a fully closed case's report reuses the closed case
type: learning
---

## Summary

Found while reviewing PR #4462 (the post-close write boundary). The post-close guard, `CaseOpenToExternalWritesNode`, cannot identify a case for `Create(CaseProposal)`. The proposal names a report, not a case, so the guard always passes.

At the CaseActor (the CASE_MANAGER), a **new** proposal from the Case Owner for the same report, sent after `case_fully_closed`, takes the accept arm of `create_case_proposal_received_tree`. `LoadExistingCaseNode` (`vultron/core/behaviors/case/nodes/proposal_case_resolution.py`) reuses the closed case. Then the arm:

- writes the proposal admission record,
- sends `Accept(CaseProposal)` for the closed case,
- runs `CommitNativeLedgerEntriesNode` against the closed case.

CM-23-013 says the CASE_MANAGER records nothing for the case after `case_fully_closed`, and ADR-0131 says it sends no reply except for a late Leave. This path appears to break both. A decline arm (`Reject(CaseProposal)`) is also reachable on a closed case.

Evidence is from reading the code: `vultron/core/behaviors/case/case_proposal_received_tree.py` (the tree has `case_id=None`, and the guard resolves no case from the proposal). A test that reproduces it is the first step.

## Decision needed

This is a reopen question, so it needs a human decision before a fix: when the Case Owner proposes a case for a report whose case is fully closed, should the CaseActor

1. refuse the proposal (drop, no reply, per ADR-0131),
2. create a new, separate case, or
3. treat it as a reopen request (#3066)?

## Pointers

- `vultron/core/behaviors/case/nodes/post_close.py` (`_candidate_case_ids`)
- `vultron/core/behaviors/case/case_proposal_received_tree.py`
- `vultron/core/behaviors/case/nodes/proposal_case_resolution.py` (`LoadExistingCaseNode`)
- ADR-0085, ADR-0131, CM-23-013, CP-05-006, CP-05-008

**Resolved**: 2026-10-12 — implementation tracked in #4468.

Decision: an owner's `Create(CaseProposal)` that resolves to its fully closed case, whether a new proposal id or a re-delivery of the original, is declined with `Reject(CaseProposal)` ("received and understood but declined", MSM-05-001), and nothing is written for the case (CM-23-013). A Reject cannot mislead, because only the Case Owner can send either proposal and the Case Owner closed the case. Reopening the existing case and creating a new case for the report are two separate paths, left to #3066 (comment posted). ADR-0131's scoping sentence is an AC on #4468, because that ADR lands with PR #4462.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4467>.
Spec: `specs/case-proposal.yaml` (CP-05-006, CP-05-008).
