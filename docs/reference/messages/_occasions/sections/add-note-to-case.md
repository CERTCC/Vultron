<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Add note to case { #add-note-to-case }

Attaches the note to the case named by the target, for example to ask or answer a question.

- **When…** a Participant posts a note to the case
- **Send:** `Add(Note)[target=VulnerabilityCase]`
- **Sent by:** not yet checked
- **How-to:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
- **Formal definition:** [General Inquiry (GI)](../../../formal_protocol/messages.md#other-message-types)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    add_note_to_case,
    json2md,
)

print(json2md(add_note_to_case()))
```
