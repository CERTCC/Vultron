<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Activate embargo { #activate-embargo }

Activates the proposal for the case. If an embargo is already active, the proposal replaces it.

- **When…** the Case Owner decides to activate a proposed embargo
- **Send:** `Accept(Event)[target=VulnerabilityCase]`
- **Sent by:** the case owner
- **Seen in:** [How to Establish an Embargo](../../../../howto/activitypub/activities/establish_embargo.md), [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    activate_embargo,
    json2md,
)

print(json2md(activate_embargo()))
```
