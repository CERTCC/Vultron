<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Reject actor recommendation { #reject-actor-recommendation }

Declines the recommender's suggestion, with `inReplyTo` naming it. The suggested actor is not invited.

- **When…** the Case Manager tells a recommender that the Case Owner declined the actor it suggested
- **Send:** `Reject(Offer(Actor)[target=VulnerabilityCase])`
- **Send to:** a participant
- **Sent by:** the case manager
- **Seen in:** [How to Suggest an Actor for a Case](../../../../howto/activitypub/activities/suggest_actor.md)
- **Formal definition:** [General Inquiry (GI)](../../../formal_protocol/messages.md#other-message-types)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    reject_actor_recommendation,
    json2md,
)

print(json2md(reject_actor_recommendation()))
```
