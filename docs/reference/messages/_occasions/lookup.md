<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Report

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| a Reporter has written up a vulnerability and is about to submit the report | `Create(VulnerabilityReport)` | an actor outside any case | any actor (usually: reporter) | — | [Create report](../rm.md#create-report) |
| a Reporter submits a vulnerability report to a Vendor or Coordinator | `Offer(VulnerabilityReport)` | an actor outside any case | any actor (usually: reporter) | — | [Report Submission (RS)](../rm.md#report-submission) |
| a report receiver has received a submitted report | `Read(Offer(VulnerabilityReport))` | an actor outside any case | the addressee of the vulnerability report offer (usually: vendor, coordinator) | — | [Report Acknowledgment (RK)](../rm.md#report-acknowledgment) |
| a report receiver judges the report valid | `Accept(Offer(VulnerabilityReport))` | the CASE_MANAGER | a participant (usually: vendor, coordinator) | — | [Validate report](../rm.md#report-valid) |
| a report receiver judges the report invalid | `TentativeReject(Offer(VulnerabilityReport))` | the CASE_MANAGER | a participant (usually: vendor, coordinator) | — | [Invalidate report](../rm.md#report-invalid) |
| a report receiver closes a report no case holds | `Reject(Offer(VulnerabilityReport))` | an actor outside any case | the addressee of the vulnerability report offer (usually: vendor, coordinator) | — | [Close report](../rm.md#report-closed) |
| a Participant accepts the case for further action | `Join(VulnerabilityCase)` | the CASE_MANAGER | a participant | — | [Report/Case Accepted (RA)](../rm.md#report-accepted) |
| a Participant defers further action on the case | `Ignore(VulnerabilityCase)` | the CASE_MANAGER | a participant | — | [Report/Case Deferred (RD)](../rm.md#report-deferred) |

## Case proposal

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| a report receiver asks a Case Actor Service to open a case for a report | `Create(CaseProposal)` | an actor outside any case | the case proposal's author (usually: vendor, coordinator) | — | [Create case proposal](../case_proposal.md#create-case-proposal) |
| a Case Actor Service agrees to open the proposed case | `Accept(CaseProposal)` | an actor outside any case | the addressee of the case proposal | — | [Accept case proposal](../case_proposal.md#accept-case-proposal) |
| a Case Actor Service declines to open the proposed case | `Reject(CaseProposal)` | an actor outside any case | the addressee of the case proposal | — | [Reject case proposal](../case_proposal.md#reject-case-proposal) |

## Case and participants

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| the CASE_MANAGER has opened a case for a submitted report | `Create(VulnerabilityCase)` | a participant | the addressee of the case proposal or vulnerability report offer | — | [Create case](../case_management.md#create-case) |
| the Case Owner links a further report to an existing case | `Add(VulnerabilityReport)[target=VulnerabilityCase]` | the CASE_MANAGER | the Case Owner | — | [Add report to case](../case_management.md#add-report-to-case) |
| the CASE_MANAGER records the new Case Owner once a case ownership transfer is accepted | `Update(VulnerabilityCase)` | a participant | internal to the CASE_MANAGER | — | [Update Case Owner](../case_management.md#update-case-owner) |
| the CASE_MANAGER brings a vulnerability item into a case, such as one a new case takes from its CSAF report | `Add(VulnerabilityItem)[target=VulnerabilityCase]` | a participant | internal to the CASE_MANAGER | — | [Add vulnerability item to case](../case_management.md#add-vulnerability-item-to-case) |
| the CASE_MANAGER brings a case reference into a case, such as one a new case takes from its CSAF report | `Add(CaseReference)[target=VulnerabilityCase]` | a participant | internal to the CASE_MANAGER | — | [Add case reference to case](../case_management.md#add-case-reference-to-case) |
| the Case Owner offers a CVD role on the case to another participant | `Offer(CaseParticipantRole)[context=VulnerabilityCase]` | the CASE_MANAGER | the Case Owner | — | [Offer case participant role](../case_management.md#offer-case-participant-role) |
| a participant accepts a role offered to it on the case | `Accept(Offer(CaseParticipantRole)[context=VulnerabilityCase])` | the CASE_MANAGER | the addressee of the case participant role offer | — | [Accept case participant role](../case_management.md#accept-case-participant-role) |
| a participant declines a role offered to it on the case | `Reject(Offer(CaseParticipantRole)[context=VulnerabilityCase])` | the CASE_MANAGER | the addressee of the case participant role offer | — | [Reject case participant role](../case_management.md#reject-case-participant-role) |
| the Case Owner proposes to transfer ownership of the case to another participant | `Offer(Offer(VulnerabilityCase))` | the CASE_MANAGER | the Case Owner | — | [Propose case ownership transfer](../case_management.md#propose-case-ownership-transfer) |
| the CASE_MANAGER offers the case to the actor the Case Owner proposed | `Offer(VulnerabilityCase)` | a participant | the CASE_MANAGER | — | [Offer case ownership transfer](../case_management.md#offer-case-ownership-transfer) |
| an actor accepts an offer of case ownership | `Accept(Offer(VulnerabilityCase))` | the CASE_MANAGER | the addressee of the vulnerability case offer | — | [Accept case ownership transfer](../case_management.md#accept-case-ownership-transfer) |
| an actor declines an offer of case ownership | `Reject(Offer(VulnerabilityCase))` | the CASE_MANAGER | the addressee of the vulnerability case offer | — | [Reject case ownership transfer](../case_management.md#reject-case-ownership-transfer) |
| the Case Owner withdraws its proposal while the offer of case ownership is open | `Undo(Offer(Offer(VulnerabilityCase)))` | the CASE_MANAGER | the Case Owner | — | [Withdraw case ownership transfer](../case_management.md#withdraw-case-ownership-transfer) |
| the CASE_MANAGER invites an actor to join the case | `Invite(Actor)[target=VulnerabilityCaseStub]` | a participant | the CASE_MANAGER | — | [Invite actor to case](../case_management.md#invite-actor-to-case) |
| an invited actor agrees to join the case | `Accept(Invite(Actor)[target=VulnerabilityCaseStub])` | the CASE_MANAGER | the invitee | — | [Accept invite to case](../case_management.md#accept-invite-to-case) |
| an invited actor declines to join the case | `Reject(Invite(Actor)[target=VulnerabilityCaseStub])` | the CASE_MANAGER | the invitee | — | [Reject invite to case](../case_management.md#reject-invite-to-case) |
| the CASE_MANAGER has replayed the case ledger to a newly joined Participant | `Invite(Actor)[target=VulnerabilityCase]` | a participant | the CASE_MANAGER | — | [Send Full-Case Invite](../case_management.md#invite-actor-to-full-case) |
| a Participant asked by a Full-Case Invite judges the case valid | `Accept(Invite(Actor)[target=VulnerabilityCase])` | the CASE_MANAGER | the invitee | — | [Accept Full-Case Invite](../case_management.md#accept-full-case-invite) |
| a Participant asked by a Full-Case Invite judges the case invalid | `TentativeReject(Invite(Actor)[target=VulnerabilityCase])` | the CASE_MANAGER | the invitee | — | [Tentatively reject Full-Case Invite](../case_management.md#tentatively-reject-full-case-invite) |
| a Participant asked by a Full-Case Invite closes the case | `Reject(Invite(Actor)[target=VulnerabilityCase])` | the CASE_MANAGER | the invitee | — | [Reject Full-Case Invite](../case_management.md#reject-full-case-invite) |
| the CASE_MANAGER has admitted a new Participant to the case | `Announce(VulnerabilityCase)` | a participant | the CASE_MANAGER | — | [Announce vulnerability case](../case_management.md#announce-vulnerability-case) |
| a Participant ends its participation in the case | `Leave(VulnerabilityCase)` | the CASE_MANAGER | the Case Owner or a participant | — | [Close case](../case_management.md#close-case) |
| the Case Owner reinstates a removed Participant | `Add(CaseParticipant)[target=VulnerabilityCase]` | the CASE_MANAGER | the Case Owner | — | [Add case participant to case](../case_management.md#add-case-participant-to-case) |
| the Case Owner removes a Participant from active participation | `Remove(CaseParticipant)[target=VulnerabilityCase]` | the CASE_MANAGER | the Case Owner | — | [Remove case participant from case](../case_management.md#remove-case-participant-from-case) |
| the CASE_MANAGER creates a participant record, such as the inert record for the invitee of a stub Invite | `Create(CaseParticipant)` | a participant | internal to the CASE_MANAGER | — | [Create case participant](../case_management.md#create-case-participant) |
| the CASE_MANAGER changes a participant record, such as moving the CASE_OWNER role on an ownership transfer | `Update(CaseParticipant)` | a participant | internal to the CASE_MANAGER | — | [Update case participant](../case_management.md#update-case-participant) |

## Embargo

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| the Case Owner terminates the active embargo | `Remove(EmbargoEvent)` | the CASE_MANAGER | the CASE_MANAGER or the Case Owner | — | [Embargo Termination (ET)](../em.md#embargo-termination) |
| the CASE_MANAGER ends the active embargo, on its own decision or on the Case Owner's | `Remove(EmbargoEvent)` | a participant | the CASE_MANAGER | — | [Tell a participant the embargo has ended](../em.md#embargo-termination-notice) |
| the CASE_MANAGER states the terms of the embargo in force | `Announce(EmbargoEvent)[context=VulnerabilityCase]` | a participant | the CASE_MANAGER | register status of the named embargo `ACTIVE` | [Announce embargo](../em.md#announce-embargo) |
| the CASE_MANAGER has applied an Embargo Termination a Case Owner sent before the end time | `Announce(EmbargoEvent)[context=VulnerabilityCase]` | a participant | the CASE_MANAGER | register status of the named embargo `TERMINATED` | [Announce embargo termination](../em.md#announce-embargo-termination) |
| a Participant proposes embargo terms for a case with no active embargo | `Invite(EmbargoEvent)[context=VulnerabilityCase]` | the CASE_MANAGER | the CASE_MANAGER or an active participant | EM state `NONE` or `PROPOSED` | [Embargo Proposal (EP)](../em.md#embargo-proposal) |
| a Participant proposes revised terms for the active embargo | `Invite(EmbargoEvent)[context=VulnerabilityCase]` | the CASE_MANAGER | the CASE_MANAGER or an active participant | EM state `ACTIVE` or `REVISE` | [Embargo Revision Proposal (EV)](../em.md#embargo-revision-proposal) |
| the CASE_MANAGER asks a Participant to answer embargo terms another Participant proposed | `Invite(EmbargoEvent)[context=VulnerabilityCase]` | a participant | the CASE_MANAGER | — | [Ask a participant about proposed embargo terms](../em.md#relay-embargo-proposal) |
| a Participant agrees to proposed embargo terms | `Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])` | the CASE_MANAGER | the invitee | EM state `PROPOSED` | [Agree to proposed embargo terms](../em.md#agree-to-embargo-proposal) |
| a Participant agrees to a proposed embargo revision | `Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])` | the CASE_MANAGER | the invitee | EM state `REVISE` | [Agree to an embargo revision](../em.md#agree-to-embargo-revision) |
| a Participant refuses proposed embargo terms | `Reject(Invite(EmbargoEvent)[context=VulnerabilityCase])` | the CASE_MANAGER | the invitee | EM state `PROPOSED` | [Refuse proposed embargo terms](../em.md#refuse-embargo-proposal) |
| a Participant refuses a proposed embargo revision | `Reject(Invite(EmbargoEvent)[context=VulnerabilityCase])` | the CASE_MANAGER | the invitee | EM state `REVISE` | [Refuse an embargo revision](../em.md#refuse-embargo-revision) |
| the CASE_MANAGER abandons an open embargo proposal it received once the case is public, an exploit is public or attacks are observed | `Reject(Invite(EmbargoEvent)[context=VulnerabilityCase])` | a participant | the CASE_MANAGER | — | [Abandon embargo proposal](../em.md#abandon-embargo-proposal) |
| the CASE_MANAGER abandons an open embargo proposal once the case is public, an exploit is public or attacks are observed | `Undo(Invite(EmbargoEvent)[context=VulnerabilityCase])` | a participant | internal to the CASE_MANAGER | — | [Withdraw an embargo invitation](../em.md#withdraw-embargo-invite) |
| the Case Owner decides to activate a proposed embargo for a case with no active embargo | `Add(EmbargoEvent)[target=VulnerabilityCase]` | the CASE_MANAGER | the Case Owner | EM state `PROPOSED` | [Embargo Proposal Acceptance (EA)](../em.md#embargo-proposal-acceptance) |
| the Case Owner decides to replace the active embargo with a proposed revision | `Add(EmbargoEvent)[target=VulnerabilityCase]` | the CASE_MANAGER | the Case Owner | EM state `REVISE` | [Embargo Revision Acceptance (EC)](../em.md#embargo-revision-acceptance) |
| the Case Owner decides to reject a proposed embargo for a case with no active embargo | `Reject(EmbargoEvent)[target=VulnerabilityCase]` | the CASE_MANAGER | the Case Owner | EM state `PROPOSED` | [Reject embargo proposal](../em.md#reject-embargo-proposal) |
| the Case Owner decides to reject a proposed revision | `Reject(EmbargoEvent)[target=VulnerabilityCase]` | the CASE_MANAGER | the Case Owner | EM state `REVISE` | [Embargo Revision Rejection (EJ)](../em.md#embargo-revision-rejection) |
| a Participant bound by the active embargo stops complying with it | `Leave(EmbargoEvent)[context=VulnerabilityCase]` | the CASE_MANAGER | a participant | — | [Withdraw from embargo](../em.md#embargo-withdrawal) |
| the CASE_MANAGER has created a case and, with it, an embargo such as the default embargo | `Create(EmbargoEvent)` | a participant | internal to the CASE_MANAGER | — | [Create embargo event](../em.md#create-embargo-event) |
| the CASE_MANAGER creates a participant's consent row for an embargo, such as the UNINVITED row a proposal writes | `Create(EmbargoConsent)` | a participant | internal to the CASE_MANAGER | — | [Create embargo consent](../em.md#create-embargo-consent) |
| the CASE_MANAGER changes a participant's consent row, such as an invitation timing out, the rows carried over at activation or a change of its own consent | `Update(EmbargoConsent)` | a participant | internal to the CASE_MANAGER | — | [Update embargo consent](../em.md#update-embargo-consent) |

## Case status

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| the CASE_MANAGER records that the public knows of the vulnerability | `Add(CaseStatus)[target=VulnerabilityCase]` | a participant | the CASE_MANAGER | `pxaState` = `Pxa` | [Public awareness in a case status](../cs.md#public-awareness) |
| the CASE_MANAGER records that an exploit for the vulnerability is public | `Add(CaseStatus)[target=VulnerabilityCase]` | a participant | the CASE_MANAGER | `pxaState` = `PXa` | [Exploit public in a case status](../cs.md#exploit-public) |
| the CASE_MANAGER records that attackers are exploiting the vulnerability | `Add(CaseStatus)[target=VulnerabilityCase]` | a participant | the CASE_MANAGER | `pxaState` = `pxA` | [Attacks observed in a case status](../cs.md#attacks-observed) |
| a Vendor becomes aware of the vulnerability | `Add(ParticipantStatus)[target=CaseParticipant]` | the CASE_MANAGER | the CASE_MANAGER or the Case Owner or the participant status's author (usually: vendor) | `vfState` = `Vf` | [Vendor Awareness (CV)](../cs.md#vendor-awareness) |
| a Vendor has a fix ready | `Add(ParticipantStatus)[target=CaseParticipant]` | the CASE_MANAGER | the CASE_MANAGER or the Case Owner or the participant status's author (usually: vendor) | `vfState` = `VF` | [Fix Readiness (CF)](../cs.md#fix-readiness) |
| a Deployer has deployed the fix | `Add(ParticipantStatus)[target=CaseParticipant]` | the CASE_MANAGER | the CASE_MANAGER or the Case Owner or the participant status's author (usually: deployer) | `dState` = `D` | [Fix Deployed (CD)](../cs.md#fix-deployed) |
| a Participant learns that the public knows of the vulnerability | `Add(ParticipantStatus)[target=CaseParticipant]` | the CASE_MANAGER | the CASE_MANAGER or the Case Owner or the participant status's author | `caseStatus.pxaState` = `Pxa` | [Public awareness in a participant status](../cs.md#participant-public-awareness) |
| a Participant learns that an exploit for the vulnerability is public | `Add(ParticipantStatus)[target=CaseParticipant]` | the CASE_MANAGER | the CASE_MANAGER or the Case Owner or the participant status's author | `caseStatus.pxaState` = `PXa` | [Exploit public in a participant status](../cs.md#participant-exploit-public) |
| a Participant observes attacks that exploit the vulnerability | `Add(ParticipantStatus)[target=CaseParticipant]` | the CASE_MANAGER | the CASE_MANAGER or the Case Owner or the participant status's author | `caseStatus.pxaState` = `pxA` | [Attacks observed in a participant status](../cs.md#participant-attacks-observed) |

## General

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| a Participant suggests an actor that the case should include | `Offer(Actor)[target=VulnerabilityCase]` | the CASE_MANAGER | a participant | sender is not the Case Owner | [Suggest actor to case](../general.md#suggest-actor-to-case) |
| the Case Owner decides to invite an actor to the case | `Offer(Actor)[target=VulnerabilityCase]` | the CASE_MANAGER | a participant | sender is the Case Owner | [Ask the CASE_MANAGER to invite an actor](../general.md#request-invite-actor-to-case) |
| the CASE_MANAGER presents a suggested actor to the Case Owner | `Offer(CaseParticipant)[target=VulnerabilityCase]` | a participant | the CASE_MANAGER | — | [Offer case participant](../general.md#offer-case-participant) |
| the Case Owner approves a suggested actor | `Accept(Offer(CaseParticipant)[target=VulnerabilityCase])` | the CASE_MANAGER | the Case Owner | — | [Accept case participant offer](../general.md#accept-case-participant-offer) |
| the Case Owner declines a suggested actor | `Reject(Offer(CaseParticipant)[target=VulnerabilityCase])` | the CASE_MANAGER | the Case Owner | — | [Reject case participant offer](../general.md#reject-case-participant-offer) |
| the CASE_MANAGER tells a recommender that the actor it suggested will be invited | `Accept(Offer(Actor)[target=VulnerabilityCase])` | a participant | the CASE_MANAGER | — | [Accept actor recommendation](../general.md#accept-actor-recommendation) |
| the CASE_MANAGER tells a recommender that the Case Owner declined the actor it suggested | `Reject(Offer(Actor)[target=VulnerabilityCase])` | a participant | the CASE_MANAGER | — | [Reject actor recommendation](../general.md#reject-actor-recommendation) |
| a Participant posts a note to the case | `Add(Note)[target=VulnerabilityCase]` | the CASE_MANAGER | an active participant | — | [Add note to case](../general.md#add-note-to-case) |
| a note's author or the Case Owner withdraws a note from the case | `Remove(Note)[target=VulnerabilityCase]` | the CASE_MANAGER | the Case Owner or the note's author | — | [Remove note from case](../general.md#remove-note-from-case) |

## Faults and acknowledgments

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| a Participant has received a message it cannot process | `Create(ProcessingFault)` | the CASE_MANAGER | an active participant | — | [Create processing fault](../faults_and_acknowledgements.md#create-processing-fault) |
| the CASE_MANAGER has refused a participant's assertion because a precondition did not hold | `Refuse(Activity)` | a participant | the CASE_MANAGER | — | [Refusal notice](../faults_and_acknowledgements.md#refusal-notice) |

## Ledger replication

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| the CASE_MANAGER has committed a case event to the case ledger | `Announce(CaseLedgerEntry)` | a participant | the CASE_MANAGER | — | [Announce case ledger entry](../ledger_replication.md#announce-case-ledger-entry) |
| a received ledger entry does not chain onto the Participant's own ledger | `Reject(CaseLedgerEntry)` | the CASE_MANAGER | an active participant, including one that has left the case | — | [Reject case ledger entry](../ledger_replication.md#reject-case-ledger-entry) |
| a Participant checks that its ledger is current, such as after a restart | `Read(CaseLedgerEntry)` | the CASE_MANAGER | a participant | — | [Read case ledger entry](../ledger_replication.md#read-case-ledger-entry) |
