---
source: CONCERN-3979
timestamp: '2026-10-01T14:50:12.091999+00:00'
title: EP-04-003's receiver default read as the CaseActor's policy; attributedTo is
  the CASE_OWNER
type: learning
---

## Observation

`ResolveEmbargoDurationNode` takes the actor default from `owner_embargo_policies(store, case.attributed_to)` (EP-04-010, #3753). Under ADR-0041 `CreateCaseFromProposalNode` attributes the new case to the **CaseActor**, and the tree runs in the CaseActor's store. So the actor default that competes under shortest-wins (EP-04-003) is an `EmbargoPolicy` published *by the CaseActor, in the CaseActor's store*. The vendor that received the report holds `CASE_OWNER` as a role, but a policy the vendor publishes on itself is never a candidate: nothing carries it to the CaseActor, and `attributed_to` does not name the vendor.

EP-04-003 says "receiver has a default"; `docs/topics/process_models/em/defaults.md` and `report_vulnerability.md` speak of the recipient's published policy; `notes/embargo-default-semantics.md` says the actor default is "the case owner's published policy" and that the CASE_MANAGER "acts as the case owner's proxy". The code agrees with none of these readings as written unless "owner" means the CaseActor.

The `report-with-embargo` demo (#3393) therefore publishes the Receiver's default on the CaseActor its node hosts, and says so. In single-container mode that is the same node; in the multi-container topology the dedicated `case-actor` container would have to carry every vendor's policy, or one policy for all cases it hosts.

## Question to decide

Whose published policy is the actor default at case creation: the CaseActor that creates and is attributed the case, or the vendor that received the report and holds CASE_OWNER? If the vendor's, how does it reach the CaseActor — carried on the `CaseProposal` (as the Reporter's terms already are, CP-01-008), or looked up from the vendor's profile (`GET /actors/{id}/embargo-policy`, EP-02-001, EP-03-001)?

## Where it is recorded today

- `notes/embargo-default-semantics.md` § "Two Kinds of Default" — the "Whose policy is the actor default" paragraphs (updated in #3393 to state the `attributed_to` fact)
- `vultron/core/behaviors/case/nodes/embargo_resolution.py` (`ResolveEmbargoDurationNode` docstring)
- `test/core/behaviors/case/test_case_proposal_received_tree.py::TestEP04SenderProposalAtCaseCreation._publish_owner_policy` publishes on `_CASE_ACTOR_URI`

Governing specs: EP-04-003, EP-04-010, EP-02-001, EP-03-001, CP-01-008, CP-05-003, ADR-0041, ADR-0096

Surfaced while building #3393.

**Resolved**: 2026-10-01 — implementation tracked in #4026, #4027, #4028.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4025>.
Spec: `specs/case-proposal.yaml` (CP-01-009, CP-01-010, CP-09-001), `specs/case-management.yaml` (CM-02-008, CM-22-001), `specs/embargo-policy.yaml` (EP-01-001, EP-02-002, EP-04-003).
Notes: `notes/embargo-default-semantics.md`, `notes/case-proposal.md`.

Root cause: ADR-0041 carried ADR-0023's "the CASE_MANAGER is the `actor` of `Create(VulnerabilityCase)`" rule over to the case's `attributedTo`, which records the case owner (CM-02-008, CM-13-001, CM-21-002). Fixed in place. The actor default is the policy on the CASE_OWNER's actor profile; in this prototype the profile travels inline as the `actor` of `Create(CaseProposal)` (project MUST), while the protocol permits a dereferenced profile reference (MAY).
