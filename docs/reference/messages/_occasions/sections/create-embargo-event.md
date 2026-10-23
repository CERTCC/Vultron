<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Create embargo event { #create-embargo-event }

Carries the new embargo in full, its start and end times included. It follows the case's genesis entry.

- **When…** the Case Manager has created a case and, with it, an embargo such as the default embargo
- **Send:** `Create(EmbargoEvent)`
- **Send to:** a participant
- **Sent by:** internal to the case manager
- **Mapping status:** [none](../../index.md#mapping-status)

Each participant learns of it from the case ledger, so it is addressed to nobody.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    create_embargo_event,
    json2md,
)

print(json2md(create_embargo_event()))
```
