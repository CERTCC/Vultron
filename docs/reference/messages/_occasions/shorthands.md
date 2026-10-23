<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

| Type | Name | Model | Wire activity |
| :---: | --- | :---: | --- |
| `RS` | Report Submission | RM | [`Offer(VulnerabilityReport)`](../rm.md#report-submission) |
| `RI` | Report Invalid | RM | [`TentativeReject(Offer(VulnerabilityReport))`](../rm.md#report-invalid), [`TentativeReject(Invite(Actor)[target=VulnerabilityCase])`](../case_management.md#tentatively-reject-full-case-invite) |
| `RV` | Report Valid | RM | [`Accept(Offer(VulnerabilityReport))`](../rm.md#report-valid), [`Accept(Invite(Actor)[target=VulnerabilityCase])`](../case_management.md#accept-full-case-invite) |
| `RD` | Report/Case Deferred | RM | [`Ignore(VulnerabilityCase)`](../rm.md#report-deferred) |
| `RA` | Report/Case Accepted | RM | [`Join(VulnerabilityCase)`](../rm.md#report-accepted) |
| `RC` | Report Closed | RM | [`Reject(Offer(VulnerabilityReport))`](../rm.md#report-closed), [`Reject(Invite(Actor)[target=VulnerabilityCase])`](../case_management.md#reject-full-case-invite) |
| `RK` | Report Acknowledgment | RM | [`Read(Offer(VulnerabilityReport))`](../rm.md#report-acknowledgment) |
| `RE` | Report Error | RM | [none](../rm.md#formal-messages-with-no-dedicated-wire-activity) |
| `EP` | Embargo Proposal | EM | [`Invite(EmbargoEvent)[context=VulnerabilityCase]`](../em.md#embargo-proposal) |
| `ER` | Embargo Proposal Rejection | EM | [`Reject(Invite(EmbargoEvent)[context=VulnerabilityCase])`](../em.md#embargo-proposal-rejection) |
| `EA` | Embargo Proposal Acceptance | EM | [`Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])`](../em.md#embargo-proposal-acceptance) |
| `EV` | Embargo Revision Proposal | EM | [`Invite(EmbargoEvent)[context=VulnerabilityCase]`](../em.md#embargo-revision-proposal) |
| `EJ` | Embargo Revision Rejection | EM | [`Reject(Invite(EmbargoEvent)[context=VulnerabilityCase])`](../em.md#embargo-revision-rejection) |
| `EC` | Embargo Revision Acceptance | EM | [`Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])`](../em.md#embargo-revision-acceptance) |
| `ET` | Embargo Termination | EM | [`Remove(EmbargoEvent)`](../em.md#embargo-termination) |
| `EK` | Embargo Acknowledgment | EM | [none](../em.md#formal-messages-with-no-dedicated-wire-activity) |
| `EE` | Embargo Error | EM | [none](../em.md#formal-messages-with-no-dedicated-wire-activity) |
| `CV` | Vendor Awareness | CS | [`Add(ParticipantStatus)[target=CaseParticipant]`](../cs.md#vendor-awareness) |
| `CF` | Fix Readiness | CS | [`Add(ParticipantStatus)[target=CaseParticipant]`](../cs.md#fix-readiness) |
| `CD` | Fix Deployed | CS | [`Add(ParticipantStatus)[target=CaseParticipant]`](../cs.md#fix-deployed) |
| `CP` | Public Awareness | CS | [`Add(CaseStatus)[target=VulnerabilityCase]`](../cs.md#public-awareness), [`Add(ParticipantStatus)[target=CaseParticipant]`](../cs.md#participant-public-awareness) |
| `CX` | Exploit Public | CS | [`Add(CaseStatus)[target=VulnerabilityCase]`](../cs.md#exploit-public), [`Add(ParticipantStatus)[target=CaseParticipant]`](../cs.md#participant-exploit-public) |
| `CA` | Attacks Observed | CS | [`Add(CaseStatus)[target=VulnerabilityCase]`](../cs.md#attacks-observed), [`Add(ParticipantStatus)[target=CaseParticipant]`](../cs.md#participant-attacks-observed) |
| `CK` | CS Acknowledgment | CS | [none](../cs.md#formal-messages-with-no-dedicated-wire-activity) |
| `CE` | CS Error | CS | [none](../cs.md#formal-messages-with-no-dedicated-wire-activity) |
| `GI` | General Inquiry | General | [`Offer(Actor)[target=VulnerabilityCase]`](../general.md#suggest-actor-to-case), [`Offer(CaseParticipant)[target=VulnerabilityCase]`](../general.md#offer-case-participant), [`Accept(Offer(CaseParticipant)[target=VulnerabilityCase])`](../general.md#accept-case-participant-offer), [`Reject(Offer(CaseParticipant)[target=VulnerabilityCase])`](../general.md#reject-case-participant-offer), [`Accept(Offer(Actor)[target=VulnerabilityCase])`](../general.md#accept-actor-recommendation), [`Reject(Offer(Actor)[target=VulnerabilityCase])`](../general.md#reject-actor-recommendation), [`Add(Note)[target=VulnerabilityCase]`](../general.md#add-note-to-case), [`Remove(Note)[target=VulnerabilityCase]`](../general.md#remove-note-from-case) |
| `GK` | General Acknowledgment | General | [none](../general.md#formal-messages-with-no-dedicated-wire-activity) |
| `GE` | General Error | General | [none](../general.md#formal-messages-with-no-dedicated-wire-activity) |
