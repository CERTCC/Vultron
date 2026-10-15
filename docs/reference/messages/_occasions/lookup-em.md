<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

| When… | Send | Sent by | Distinguished by | Details |
|---|---|---|---|---|
| the Case Owner terminates the active embargo | `Remove(Event)` | the case manager or the case owner | — | [Embargo Termination (ET)](../em.md#embargo-termination) |
| the Case Manager states the terms of the embargo in force | `Announce(Event)[context=VulnerabilityCase]` | the case manager | — | [Announce embargo](../em.md#announce-embargo) |
| a Participant proposes embargo terms for a case with no active embargo | `Invite(Event)[context=VulnerabilityCase]` | the case manager or an active participant | EM state `NONE` or `PROPOSED` | [Embargo Proposal (EP)](../em.md#embargo-proposal) |
| a Participant proposes revised terms for the active embargo | `Invite(Event)[context=VulnerabilityCase]` | the case manager or an active participant | EM state `ACTIVE` or `REVISE` | [Embargo Revision Proposal (EV)](../em.md#embargo-revision-proposal) |
| a Participant agrees to proposed embargo terms | `Accept(Invite(Event)[context=VulnerabilityCase])` | the invitee | EM state `PROPOSED` | [Embargo Proposal Acceptance (EA)](../em.md#embargo-proposal-acceptance) |
| a Participant agrees to a proposed embargo revision | `Accept(Invite(Event)[context=VulnerabilityCase])` | the invitee | EM state `REVISE` | [Embargo Revision Acceptance (EC)](../em.md#embargo-revision-acceptance) |
| a Participant refuses proposed embargo terms | `Reject(Invite(Event)[context=VulnerabilityCase])` | the invitee | EM state `PROPOSED` | [Embargo Proposal Rejection (ER)](../em.md#embargo-proposal-rejection) |
| a Participant refuses a proposed embargo revision | `Reject(Invite(Event)[context=VulnerabilityCase])` | the invitee | EM state `REVISE` | [Embargo Revision Rejection (EJ)](../em.md#embargo-revision-rejection) |
| the Case Owner decides to activate a proposed embargo | `Accept(Event)[target=VulnerabilityCase]` | the case owner | — | [Activate embargo](../em.md#activate-embargo) |
| the Case Owner decides to reject a proposed embargo | `Reject(Event)[target=VulnerabilityCase]` | the case owner | — | [Reject embargo proposal](../em.md#reject-embargo-proposal) |
