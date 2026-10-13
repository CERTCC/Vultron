<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Create note { #create-note }

Mints a note for the case. It precedes the Add that attaches it.

- **When…** a Participant has written a note it is about to post to the case
- **Send:** `Create(Note)`
- **Sent by:** not yet checked
- **How-to:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
- **Formal definition:** [General Inquiry (GI)](../../../formal_protocol/messages.md#other-message-types)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    create_note,
    json2md,
)

print(json2md(create_note()))
```
