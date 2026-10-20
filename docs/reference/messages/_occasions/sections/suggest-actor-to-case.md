<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Suggest actor to case { #suggest-actor-to-case }

Recommends an actor to the Case Manager for the case named by the target.

- **When…** a Participant suggests an actor that the case should include
- **Send:** `Offer(Actor)[target=VulnerabilityCase]`
- **Send to:** the case manager
- **Sent by:** a participant
- **Distinguished by:** sender is not the case owner
- **Seen in:** [How to Suggest an Actor for a Case](../../../../howto/activitypub/activities/suggest_actor.md)
- **Formal definition:** [General Inquiry (GI)](../../../formal_protocol/messages.md#other-message-types)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    recommend_actor,
    json2md,
)

print(json2md(recommend_actor()))
```
