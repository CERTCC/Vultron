<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Fix Readiness (CF) { #fix-readiness }

Announces that the Vendor whose participant record is the target has a fix ready.

- **When…** a Vendor has a fix ready
- **Send:** `Add(ParticipantStatus)[target=CaseParticipant]`
- **Sent by:** an active participant (usually: vendor)
- **Distinguished by:** `vf_state` = `VF`
- **How-to:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
- **Formal definition:** [Fix Readiness (CF)](../../../formal_protocol/messages.md#cs-message-types)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    add_fix_readiness_to_participant,
    json2md,
)

print(json2md(add_fix_readiness_to_participant()))
```
