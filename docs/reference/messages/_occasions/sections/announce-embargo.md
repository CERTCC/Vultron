<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Announce embargo { #announce-embargo }

Tells participants the terms of the active embargo. It proposes nothing.

- **When…** the Case Manager states the terms of the embargo in force
- **Send:** `Announce(Event)[context=VulnerabilityCase]`
- **Send to:** a participant
- **Sent by:** the case manager
- **Seen in:** [How to Establish an Embargo](../../../../howto/activitypub/activities/establish_embargo.md), [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    announce_embargo,
    json2md,
)

print(json2md(announce_embargo()))
```
