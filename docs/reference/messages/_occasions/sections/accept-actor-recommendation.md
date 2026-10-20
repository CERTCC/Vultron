<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Accept actor recommendation { #accept-actor-recommendation }

Accepts the recommender's suggestion, with `inReplyTo` naming it. The Case Manager sends it once the Case Owner approves, or at once when the suggested actor is already invited or has joined.

- **When…** the Case Manager tells a recommender that the actor it suggested will be invited
- **Send:** `Accept(Offer(Actor)[target=VulnerabilityCase])`
- **Send to:** a participant
- **Sent by:** the case manager
- **Seen in:** [How to Suggest an Actor for a Case](../../../../howto/activitypub/activities/suggest_actor.md)
- **Formal definition:** [General Inquiry (GI)](../../../formal_protocol/messages.md#other-message-types)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    accept_actor_recommendation,
    json2md,
)

print(json2md(accept_actor_recommendation()))
```
