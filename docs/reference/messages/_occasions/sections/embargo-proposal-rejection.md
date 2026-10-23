<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Embargo Proposal Rejection (ER) { #embargo-proposal-rejection }

Records the sender's own refusal of the proposed terms. The proposal is rejected for the case only when the Case Owner sends its decision.

- **When…** a Participant refuses proposed embargo terms
- **Send:** `Reject(Invite(Event)[context=VulnerabilityCase])`
- **Send to:** the case manager
- **Sent by:** the invitee
- **Distinguished by:** EM state `PROPOSED`
- **Seen in:** [How to Establish an Embargo](../../../../howto/activitypub/activities/establish_embargo.md)
- **Formal definition:** [Embargo Proposal Rejection (ER)](../../../formal_protocol/messages.md#em-message-types)
- **Mapping status:** [collapse](../../index.md#mapping-status)

The Case Manager sends the same activity when it abandons an open proposal once the case is public, an exploit is public or attacks are observed. Its Reject cancels the proposal, and each Invite it relayed for the proposal is then withdrawn.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    reject_embargo,
    json2md,
)

print(json2md(reject_embargo()))
```
