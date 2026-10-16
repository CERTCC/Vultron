<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Create note { #create-note }

Creates a note and, when the note's context names the case, posts it to that case: the Case Manager attaches the note and records the attachment in the case ledger. The Create carries no target. A receiver also accepts a Create followed by an Add of the same note, and the Add then changes nothing more.

- **When…** a Participant posts a new note to the case
- **Send:** `Create(Note)`
- **Send to:** the case manager
- **Sent by:** an active participant
- **Seen in:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
- **Formal definition:** [General Inquiry (GI)](../../../formal_protocol/messages.md#other-message-types)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    create_note,
    json2md,
)

print(json2md(create_note()))
```
