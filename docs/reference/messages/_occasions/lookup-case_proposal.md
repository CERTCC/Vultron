<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

| When… | Send | Sent by | Distinguished by | Details |
|---|---|---|---|---|
| a report receiver asks a Case Actor Service to open a case for a report | `Create(CaseProposal)` | not yet checked (usually: vendor, coordinator) | — | [Create case proposal](../case_proposal.md#create-case-proposal) |
| a Case Actor Service agrees to open the proposed case | `Accept(CaseProposal)` | the addressee of the case proposal | — | [Accept case proposal](../case_proposal.md#accept-case-proposal) |
| a Case Actor Service declines to open the proposed case | `Reject(CaseProposal)` | the addressee of the case proposal | — | [Reject case proposal](../case_proposal.md#reject-case-proposal) |
