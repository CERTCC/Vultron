<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Public Awareness (CP) { #public-awareness }

Announces evidence that the vulnerability is known to the public.

- **When…** a Participant learns that the public knows of the vulnerability
- **Send:** `Add(CaseStatus)[target=VulnerabilityCase]`
- **Sent by:** not yet checked
- **Distinguished by:** `pxa_state` = `Pxa`
- **Seen in:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
- **Formal definition:** [Public Awareness (CP)](../../../formal_protocol/messages.md#cs-message-types)
- **Mapping status:** [collapse](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    add_public_awareness_to_case,
    json2md,
)

print(json2md(add_public_awareness_to_case()))
```
