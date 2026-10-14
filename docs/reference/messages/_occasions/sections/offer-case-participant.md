<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Offer case participant { #offer-case-participant }

Forwards the recommendation as a proposed participant record, carrying the original recommendation's ID and the default roles it assigned.

- **When…** the Case Manager presents a suggested actor to the Case Owner
- **Send:** `Offer(CaseParticipant)[target=VulnerabilityCase]`
- **Sent by:** the case manager
- **Seen in:** [How to Suggest an Actor for a Case](../../../../howto/activitypub/activities/suggest_actor.md)
- **Formal definition:** [General Inquiry (GI)](../../../formal_protocol/messages.md#other-message-types)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    offer_case_participant,
    json2md,
)

print(json2md(offer_case_participant()))
```
