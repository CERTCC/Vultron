<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Reject embargo proposal { #reject-embargo-proposal }

Rejects the proposal for the case. An active embargo stays in force on its current terms.

- **When…** the Case Owner decides to reject a proposed embargo
- **Send:** `Reject(Event)[target=VulnerabilityCase]`
- **Sent by:** the case owner
- **How-to:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    reject_embargo_proposal,
    json2md,
)

print(json2md(reject_embargo_proposal()))
```
