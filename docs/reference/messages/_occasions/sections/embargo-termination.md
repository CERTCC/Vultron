<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Embargo Termination (ET) { #embargo-termination }

Terminates the embargo with immediate effect.

- **When…** the Case Owner terminates the active embargo
- **Send:** `Remove(Event)`
- **Sent by:** the case owner
- **Seen in:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
- **Formal definition:** [Embargo Termination (ET)](../../../formal_protocol/messages.md#em-message-types)
- **Mapping status:** [direct](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    remove_embargo,
    json2md,
)

print(json2md(remove_embargo()))
```
