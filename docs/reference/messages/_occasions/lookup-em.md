<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| the Case Owner terminates the active embargo | `Remove(Event)` | the case manager | the case manager or the case owner | — | [Embargo Termination (ET)](../em.md#embargo-termination) |
| the Case Manager ends the active embargo, on its own decision or on the Case Owner's | `Remove(Event)` | a participant | the case manager | — | [Tell a participant the embargo has ended](../em.md#embargo-termination-notice) |
| the Case Manager states the terms of the embargo in force | `Announce(Event)[context=VulnerabilityCase]` | a participant | the case manager | — | [Announce embargo](../em.md#announce-embargo) |
| the Case Manager has applied an Embargo Termination a Case Owner sent before the end time | `Announce(Event)[context=VulnerabilityCase]` | a participant | the case manager | — | [Announce embargo termination](../em.md#announce-embargo-termination) |
| a Participant proposes embargo terms for a case with no active embargo | `Invite(Event)[context=VulnerabilityCase]` | the case manager | the case manager or an active participant | EM state `NONE` or `PROPOSED` | [Embargo Proposal (EP)](../em.md#embargo-proposal) |
| a Participant proposes revised terms for the active embargo | `Invite(Event)[context=VulnerabilityCase]` | the case manager | the case manager or an active participant | EM state `ACTIVE` or `REVISE` | [Embargo Revision Proposal (EV)](../em.md#embargo-revision-proposal) |
| the Case Manager asks a Participant to answer embargo terms another Participant proposed | `Invite(Event)[context=VulnerabilityCase]` | a participant | the case manager | — | [Ask a participant about proposed embargo terms](../em.md#relay-embargo-proposal) |
| a Participant agrees to proposed embargo terms | `Accept(Invite(Event)[context=VulnerabilityCase])` | the case manager | the invitee | EM state `PROPOSED` | [Embargo Proposal Acceptance (EA)](../em.md#embargo-proposal-acceptance) |
| a Participant agrees to a proposed embargo revision | `Accept(Invite(Event)[context=VulnerabilityCase])` | the case manager | the invitee | EM state `REVISE` | [Embargo Revision Acceptance (EC)](../em.md#embargo-revision-acceptance) |
| a Participant refuses proposed embargo terms | `Reject(Invite(Event)[context=VulnerabilityCase])` | the case manager | the invitee | EM state `PROPOSED` | [Embargo Proposal Rejection (ER)](../em.md#embargo-proposal-rejection) |
| a Participant refuses a proposed embargo revision | `Reject(Invite(Event)[context=VulnerabilityCase])` | the case manager | the invitee | EM state `REVISE` | [Embargo Revision Rejection (EJ)](../em.md#embargo-revision-rejection) |
| the Case Owner decides to activate a proposed embargo | `Accept(Event)[target=VulnerabilityCase]` | the case manager | the case owner | — | [Activate embargo](../em.md#activate-embargo) |
| the Case Owner decides to reject a proposed embargo | `Reject(Event)[target=VulnerabilityCase]` | the case manager | the case owner | — | [Reject embargo proposal](../em.md#reject-embargo-proposal) |
| a Participant bound by the active embargo stops complying with it | `Leave(Event)[context=VulnerabilityCase]` | the case manager | a participant | — | [Withdraw from embargo](../em.md#embargo-withdrawal) |
