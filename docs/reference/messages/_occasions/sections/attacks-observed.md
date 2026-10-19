<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Attacks observed in a case status { #attacks-observed }

Announces evidence that attackers are exploiting the vulnerability.

- **When…** a Participant observes attacks that exploit the vulnerability
- **Send:** `Add(CaseStatus)[target=VulnerabilityCase]`
- **Send to:** the case manager
- **Sent by:** a participant
- **Distinguished by:** `pxaState` = `pxA`
- **Seen in:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
- **Formal definition:** [Attacks Observed (CA)](../../../formal_protocol/messages.md#cs-message-types)
- **Mapping status:** [collapse](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    add_attacks_observed_to_case,
    json2md,
)

print(json2md(add_attacks_observed_to_case()))
```
