<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Reject case participant offer { #reject-case-participant-offer }

Rejects the proposed participant record. The Case Manager tells the recommender.

- **When…** the Case Owner declines a suggested actor
- **Send:** `Reject(Offer(CaseParticipant)[target=VulnerabilityCase])`
- **Sent by:** the case owner
- **How-to:** [How to Suggest an Actor for a Case](../../../../howto/activitypub/activities/suggest_actor.md)
- **Formal definition:** [General Inquiry (GI)](../../../formal_protocol/messages.md#other-message-types)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    reject_case_participant_offer,
    json2md,
)

print(json2md(reject_case_participant_offer()))
```
