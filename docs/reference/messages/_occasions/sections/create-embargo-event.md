<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Create embargo event { #create-embargo-event }

Mints the embargo event that carries the proposed terms. It precedes the Invite that proposes them.

- **When…** a Participant has drafted embargo terms it is about to propose
- **Send:** `Create(Event)[context=VulnerabilityCase|VulnerabilityReport]`
- **Sent by:** the case manager or the case owner
- **Seen in:** [How to Establish an Embargo](../../../../howto/activitypub/activities/establish_embargo.md)
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    create_embargo_event,
    json2md,
)

print(json2md(create_embargo_event()))
```
