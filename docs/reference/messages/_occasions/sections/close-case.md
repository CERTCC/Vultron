<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Close case { #close-case }

Leaves the case, moving the sender's RM state to Closed.

- **When…** a Participant ends its participation in the case
- **Send:** `Leave(VulnerabilityCase)`
- **Sent by:** not yet checked
- **How-to:** [How to Advance a Case Through Report Management](../../../../howto/activitypub/activities/manage_case.md)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    close_case,
    json2md,
)

print(json2md(close_case()))
```
