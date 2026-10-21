<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Public awareness in a case status { #public-awareness }

Tells a participant that the case status now records that the public knows of the vulnerability.

- **When…** the Case Manager records that the public knows of the vulnerability
- **Send:** `Add(CaseStatus)[target=VulnerabilityCase]`
- **Send to:** a participant
- **Sent by:** the case manager
- **Distinguished by:** `pxaState` = `Pxa`
- **Formal definition:** [Public Awareness (CP)](../../../formal_protocol/messages.md#cs-message-types)
- **Mapping status:** [collapse](../../index.md#mapping-status)

Only the Case Manager sends a case status, as its record of the `pxaState` it adopted, and a receiver refuses one from any other sender. A participant reports public awareness, a public exploit or observed attacks in its own participant status instead.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    add_public_awareness_to_case,
    json2md,
)

print(json2md(add_public_awareness_to_case()))
```
