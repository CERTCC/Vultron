<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Vendor Awareness (CV) { #vendor-awareness }

Announces that the report has reached the Vendor whose participant record is the target.

- **When…** a Vendor becomes aware of the vulnerability
- **Send:** `Add(ParticipantStatus)[target=CaseParticipant]`
- **Sent by:** an active participant (usually: vendor)
- **Distinguished by:** `vf_state` = `Vf`
- **How-to:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
- **Formal definition:** [Vendor Awareness (CV)](../../../formal_protocol/messages.md#cs-message-types)
- **Mapping status:** [collapse](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    add_vendor_awareness_to_participant,
    json2md,
)

print(json2md(add_vendor_awareness_to_participant()))
```
