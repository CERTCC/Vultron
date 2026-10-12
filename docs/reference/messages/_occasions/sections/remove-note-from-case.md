<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Remove note from case { #remove-note-from-case }

Removes the note from the case named by the target.

- **When…** a note's author or the Case Owner withdraws a note from the case
- **Send:** `Remove(Note)[target=VulnerabilityCase]`
- **Sent by:** an active participant
- **How-to:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
- **Formal definition:** [General Inquiry (GI)](../../../formal_protocol/messages.md#other-message-types)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    remove_note_from_case,
    json2md,
)

print(json2md(remove_note_from_case()))
```
