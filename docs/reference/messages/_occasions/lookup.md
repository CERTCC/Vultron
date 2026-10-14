<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Report

| When… | Send | Sent by | Distinguished by | Details |
|---|---|---|---|---|
| a Reporter has written up a vulnerability and is about to submit the report | `Create(VulnerabilityReport)` | any actor (usually: finder, reporter) | — | [Create report](../rm.md#create-report) |
| a Reporter submits a vulnerability report to a Vendor or Coordinator | `Offer(VulnerabilityReport)` | any actor (usually: reporter) | — | [Report Submission (RS)](../rm.md#report-submission) |
| a report receiver has read a submitted report | `Read(Offer(VulnerabilityReport))` | the addressee of the vulnerability report (usually: vendor, coordinator) | — | [Report Acknowledgment (RK)](../rm.md#report-acknowledgment) |
| a report receiver judges the report valid | `Accept(Offer(VulnerabilityReport))` | an active participant (usually: vendor, coordinator) | — | [Validate report](../rm.md#report-valid) |
| a report receiver judges the report invalid | `TentativeReject(Offer(VulnerabilityReport))` | an active participant (usually: vendor, coordinator) | — | [Invalidate report](../rm.md#report-invalid) |
| a report receiver closes the report | `Reject(Offer(VulnerabilityReport))` | an active participant (usually: vendor, coordinator) | — | [Close report](../rm.md#report-closed) |
| a Participant accepts the case for further action | `Join(VulnerabilityCase)` | an active participant | — | [Report/Case Accepted (RA)](../rm.md#report-accepted) |
| a Participant defers further action on the case | `Ignore(VulnerabilityCase)` | an active participant | — | [Report/Case Deferred (RD)](../rm.md#report-deferred) |

## Case proposal

| When… | Send | Sent by | Distinguished by | Details |
|---|---|---|---|---|
| a report receiver asks a Case Actor Service to open a case for a report | `Create(CaseProposal)` | not yet checked (usually: vendor, coordinator) | — | [Create case proposal](../case_proposal.md#create-case-proposal) |
| a Case Actor Service agrees to open the proposed case | `Accept(CaseProposal)` | the addressee of the case proposal | — | [Accept case proposal](../case_proposal.md#accept-case-proposal) |
| a Case Actor Service declines to open the proposed case | `Reject(CaseProposal)` | the addressee of the case proposal | — | [Reject case proposal](../case_proposal.md#reject-case-proposal) |

## Case and participants

| When… | Send | Sent by | Distinguished by | Details |
|---|---|---|---|---|
| the Case Manager has opened a case for a submitted report | `Create(VulnerabilityCase)` | not yet checked | — | [Create case](../case_management.md#create-case) |
| the Case Owner links a further report to an existing case | `Add(VulnerabilityReport)[target=VulnerabilityCase]` | the case owner | — | [Add report to case](../case_management.md#add-report-to-case) |
| a Participant offers a CVD role on the case to another actor | `Offer(CaseParticipantRole)[context=VulnerabilityCase]` | not yet checked | — | [Offer case participant role](../case_management.md#offer-case-participant-role) |
| an actor accepts a role offered to it on the case | `Accept(Offer(CaseParticipantRole)[context=VulnerabilityCase])` | not yet checked | — | [Accept case participant role](../case_management.md#accept-case-participant-role) |
| an actor declines a role offered to it on the case | `Reject(Offer(CaseParticipantRole)[context=VulnerabilityCase])` | not yet checked | — | [Reject case participant role](../case_management.md#reject-case-participant-role) |
| the Case Owner offers to transfer ownership of the case to another actor | `Offer(VulnerabilityCase)` | not yet checked | — | [Offer case ownership transfer](../case_management.md#offer-case-ownership-transfer) |
| an actor accepts an offer of case ownership | `Accept(Offer(VulnerabilityCase))` | the addressee of the vulnerability case | — | [Accept case ownership transfer](../case_management.md#accept-case-ownership-transfer) |
| an actor declines an offer of case ownership | `Reject(Offer(VulnerabilityCase))` | the addressee of the vulnerability case | — | [Reject case ownership transfer](../case_management.md#reject-case-ownership-transfer) |
| the Case Owner withdraws an open offer of case ownership | `Undo(Offer(VulnerabilityCase))` | the case owner | — | [Withdraw case ownership transfer](../case_management.md#withdraw-case-ownership-transfer) |
| the Case Manager invites an actor to join the case | `Invite(Actor)[target=VulnerabilityCaseStub]` | not yet checked | — | [Invite actor to case](../case_management.md#invite-actor-to-case) |
| an invited actor agrees to join the case | `Accept(Invite(Actor)[target=VulnerabilityCaseStub])` | the invitee | — | [Accept invite to case](../case_management.md#accept-invite-to-case) |
| an invited actor declines to join the case | `Reject(Invite(Actor)[target=VulnerabilityCaseStub])` | the invitee | — | [Reject invite to case](../case_management.md#reject-invite-to-case) |
| the Case Manager has replayed the case ledger to a newly joined Participant | `Invite(Actor)[target=VulnerabilityCase]` | the case manager | — | [Send Full-Case Invite](../case_management.md#invite-actor-to-full-case) |
| a Participant asked by a Full-Case Invite judges the case valid | `Accept(Invite(Actor)[target=VulnerabilityCase])` | the invitee | — | [Accept Full-Case Invite](../case_management.md#accept-full-case-invite) |
| a Participant asked by a Full-Case Invite judges the case invalid | `TentativeReject(Invite(Actor)[target=VulnerabilityCase])` | the invitee | — | [Tentatively reject Full-Case Invite](../case_management.md#tentatively-reject-full-case-invite) |
| a Participant asked by a Full-Case Invite closes the case | `Reject(Invite(Actor)[target=VulnerabilityCase])` | the invitee | — | [Reject Full-Case Invite](../case_management.md#reject-full-case-invite) |
| the Case Manager has admitted a new Participant to the case | `Announce(VulnerabilityCase)` | not yet checked | — | [Announce vulnerability case](../case_management.md#announce-vulnerability-case) |
| a Participant ends its participation in the case | `Leave(VulnerabilityCase)` | not yet checked | — | [Close case](../case_management.md#close-case) |
| a Participant is about to add an actor's participant record to the case | `Create(CaseParticipant)[context=VulnerabilityCase]` | not yet checked | — | [Create case participant](../case_management.md#create-case-participant) |
| the Case Owner reinstates a removed Participant | `Add(CaseParticipant)[target=VulnerabilityCase]` | the case owner | — | [Add case participant to case](../case_management.md#add-case-participant-to-case) |
| the Case Owner removes a Participant from active participation | `Remove(CaseParticipant)[target=VulnerabilityCase]` | the case owner | — | [Remove case participant from case](../case_management.md#remove-case-participant-from-case) |

## Embargo

| When… | Send | Sent by | Distinguished by | Details |
|---|---|---|---|---|
| a Participant has drafted embargo terms it is about to propose | <code>Create(Event)&#91;context=VulnerabilityCase&#124;VulnerabilityReport&#93;</code> | the case owner | — | [Create embargo event](../em.md#create-embargo-event) |
| the Case Owner terminates the active embargo | `Remove(Event)` | the case owner | — | [Embargo Termination (ET)](../em.md#embargo-termination) |
| the Case Manager states the terms of the embargo in force | `Announce(Event)[context=VulnerabilityCase]` | the case manager | — | [Announce embargo](../em.md#announce-embargo) |
| a Participant proposes embargo terms for a case with no active embargo | `Invite(Event)[context=VulnerabilityCase]` | an active participant | EM state `NONE` or `PROPOSED` | [Embargo Proposal (EP)](../em.md#embargo-proposal) |
| a Participant proposes revised terms for the active embargo | `Invite(Event)[context=VulnerabilityCase]` | an active participant | EM state `ACTIVE` or `REVISE` | [Embargo Revision Proposal (EV)](../em.md#embargo-revision-proposal) |
| a Participant agrees to proposed embargo terms | `Accept(Invite(Event)[context=VulnerabilityCase])` | the invitee | EM state `PROPOSED` | [Embargo Proposal Acceptance (EA)](../em.md#embargo-proposal-acceptance) |
| a Participant agrees to a proposed embargo revision | `Accept(Invite(Event)[context=VulnerabilityCase])` | the invitee | EM state `REVISE` | [Embargo Revision Acceptance (EC)](../em.md#embargo-revision-acceptance) |
| a Participant refuses proposed embargo terms | `Reject(Invite(Event)[context=VulnerabilityCase])` | the invitee | EM state `PROPOSED` | [Embargo Proposal Rejection (ER)](../em.md#embargo-proposal-rejection) |
| a Participant refuses a proposed embargo revision | `Reject(Invite(Event)[context=VulnerabilityCase])` | the invitee | EM state `REVISE` | [Embargo Revision Rejection (EJ)](../em.md#embargo-revision-rejection) |
| the Case Owner decides to activate a proposed embargo | `Accept(Event)[target=VulnerabilityCase]` | the case owner | — | [Activate embargo](../em.md#activate-embargo) |
| the Case Owner decides to reject a proposed embargo | `Reject(Event)[target=VulnerabilityCase]` | the case owner | — | [Reject embargo proposal](../em.md#reject-embargo-proposal) |

## Case status

| When… | Send | Sent by | Distinguished by | Details |
|---|---|---|---|---|
| a Participant is about to announce a change to the public state of the case | `Create(CaseStatus)[context=VulnerabilityCase]` | not yet checked | — | [Create case status](../cs.md#create-case-status) |
| a Participant learns that the public knows of the vulnerability | `Add(CaseStatus)[target=VulnerabilityCase]` | not yet checked | `pxaState` = `Pxa` | [Public Awareness (CP)](../cs.md#public-awareness) |
| a Participant learns that an exploit for the vulnerability is public | `Add(CaseStatus)[target=VulnerabilityCase]` | not yet checked | `pxaState` = `PXa` | [Exploit Public (CX)](../cs.md#exploit-public) |
| a Participant observes attacks that exploit the vulnerability | `Add(CaseStatus)[target=VulnerabilityCase]` | not yet checked | `pxaState` = `pxA` | [Attacks Observed (CA)](../cs.md#attacks-observed) |
| a Participant is about to announce a change to its own state in the case | `Create(ParticipantStatus)` | not yet checked | — | [Create participant status](../cs.md#create-participant-status) |
| a Vendor becomes aware of the vulnerability | `Add(ParticipantStatus)[target=CaseParticipant]` | an active participant (usually: vendor) | `vfState` = `Vf` | [Vendor Awareness (CV)](../cs.md#vendor-awareness) |
| a Vendor has a fix ready | `Add(ParticipantStatus)[target=CaseParticipant]` | an active participant (usually: vendor) | `vfState` = `VF` | [Fix Readiness (CF)](../cs.md#fix-readiness) |
| a Deployer has deployed the fix | `Add(ParticipantStatus)[target=CaseParticipant]` | an active participant (usually: deployer) | `dState` = `D` | [Fix Deployed (CD)](../cs.md#fix-deployed) |

## General

| When… | Send | Sent by | Distinguished by | Details |
|---|---|---|---|---|
| a Participant suggests an actor that the case should include | `Offer(Actor)[target=VulnerabilityCase]` | an active participant | — | [Suggest actor to case](../general.md#suggest-actor-to-case) |
| the Case Manager presents a suggested actor to the Case Owner | `Offer(CaseParticipant)[target=VulnerabilityCase]` | the case manager | — | [Offer case participant](../general.md#offer-case-participant) |
| the Case Owner approves a suggested actor | `Accept(Offer(CaseParticipant)[target=VulnerabilityCase])` | the case owner | — | [Accept case participant offer](../general.md#accept-case-participant-offer) |
| the Case Owner declines a suggested actor | `Reject(Offer(CaseParticipant)[target=VulnerabilityCase])` | the case owner | — | [Reject case participant offer](../general.md#reject-case-participant-offer) |
| a Participant has written a note it is about to post to the case | `Create(Note)` | not yet checked | — | [Create note](../general.md#create-note) |
| a Participant posts a note to the case | `Add(Note)[target=VulnerabilityCase]` | not yet checked | — | [Add note to case](../general.md#add-note-to-case) |
| a note's author or the Case Owner withdraws a note from the case | `Remove(Note)[target=VulnerabilityCase]` | an active participant | — | [Remove note from case](../general.md#remove-note-from-case) |

## Faults and acknowledgments

| When… | Send | Sent by | Distinguished by | Details |
|---|---|---|---|---|
| a Participant has received a message it cannot process | `Create(ProcessingFault)` | not yet checked | — | [Create processing fault](../faults_and_acknowledgements.md#create-processing-fault) |

## Ledger replication

| When… | Send | Sent by | Distinguished by | Details |
|---|---|---|---|---|
| the Case Manager has committed a case event to the case ledger | `Announce(CaseLedgerEntry)` | the case manager | — | [Announce case ledger entry](../ledger_replication.md#announce-case-ledger-entry) |
| a received ledger entry does not chain onto the Participant's own ledger | `Reject(CaseLedgerEntry)` | an active participant | — | [Reject case ledger entry](../ledger_replication.md#reject-case-ledger-entry) |
