<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| a Participant suggests an actor that the case should include | `Offer(Actor)[target=VulnerabilityCase]` | the case manager | a participant | sender is not the case owner | [Suggest actor to case](../general.md#suggest-actor-to-case) |
| the Case Owner decides to invite an actor to the case | `Offer(Actor)[target=VulnerabilityCase]` | the case manager | a participant | sender is the case owner | [Ask the Case Manager to invite an actor](../general.md#request-invite-actor-to-case) |
| the Case Manager presents a suggested actor to the Case Owner | `Offer(CaseParticipant)[target=VulnerabilityCase]` | a participant | the case manager | — | [Offer case participant](../general.md#offer-case-participant) |
| the Case Owner approves a suggested actor | `Accept(Offer(CaseParticipant)[target=VulnerabilityCase])` | the case manager | the case owner | — | [Accept case participant offer](../general.md#accept-case-participant-offer) |
| the Case Owner declines a suggested actor | `Reject(Offer(CaseParticipant)[target=VulnerabilityCase])` | the case manager | the case owner | — | [Reject case participant offer](../general.md#reject-case-participant-offer) |
| the Case Manager tells a recommender that the actor it suggested will be invited | `Accept(Offer(Actor)[target=VulnerabilityCase])` | a participant | the case manager | — | [Accept actor recommendation](../general.md#accept-actor-recommendation) |
| the Case Manager tells a recommender that the Case Owner declined the actor it suggested | `Reject(Offer(Actor)[target=VulnerabilityCase])` | a participant | the case manager | — | [Reject actor recommendation](../general.md#reject-actor-recommendation) |
| a Participant posts a note to the case | `Add(Note)[target=VulnerabilityCase]` | the case manager | an active participant | — | [Add note to case](../general.md#add-note-to-case) |
| a note's author or the Case Owner withdraws a note from the case | `Remove(Note)[target=VulnerabilityCase]` | the case manager | the case owner or the note's author | — | [Remove note from case](../general.md#remove-note-from-case) |
