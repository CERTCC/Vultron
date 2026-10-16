<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| a Participant suggests an actor that the case should include | `Offer(Actor)[target=VulnerabilityCase]` | the case manager | a participant | — | [Suggest actor to case](../general.md#suggest-actor-to-case) |
| the Case Owner decides to invite an actor to the case | `Offer(Actor)[target=VulnerabilityCase]` | the case manager | a participant (usually: case owner) | — | [Ask the Case Manager to invite an actor](../general.md#request-invite-actor-to-case) |
| the Case Manager presents a suggested actor to the Case Owner | `Offer(CaseParticipant)[target=VulnerabilityCase]` | a participant | the case manager | — | [Offer case participant](../general.md#offer-case-participant) |
| the Case Owner approves a suggested actor | `Accept(Offer(CaseParticipant)[target=VulnerabilityCase])` | the case manager | the case owner | — | [Accept case participant offer](../general.md#accept-case-participant-offer) |
| the Case Owner declines a suggested actor | `Reject(Offer(CaseParticipant)[target=VulnerabilityCase])` | the case manager | the case owner | — | [Reject case participant offer](../general.md#reject-case-participant-offer) |
| a Participant posts a note to the case | `Add(Note)[target=VulnerabilityCase]` | the case manager | not yet checked | — | [Add note to case](../general.md#add-note-to-case) |
| a note's author or the Case Owner withdraws a note from the case | `Remove(Note)[target=VulnerabilityCase]` | the case manager | the case owner or the note's author | — | [Remove note from case](../general.md#remove-note-from-case) |
