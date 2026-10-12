<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Embargo Proposal Rejection (ER) { #embargo-proposal-rejection }

Records the sender's own refusal of the proposed terms. The proposal is rejected for the case only when the Case Owner sends its decision.

- **When…** a Participant refuses proposed embargo terms
- **Send:** `Reject(Invite(Event)[context=VulnerabilityCase])`
- **Sent by:** the invitee
- **Distinguished by:** EM state `PROPOSED`
- **How-to:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
- **Formal definition:** [Embargo Proposal Rejection (ER)](../../../formal_protocol/messages.md#em-message-types)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    reject_embargo,
    json2md,
)

print(json2md(reject_embargo()))
```
