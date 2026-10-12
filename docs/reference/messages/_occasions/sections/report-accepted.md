<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Report/Case Accepted (RA) { #report-accepted }

Joins the case, moving the sender's RM state to Accepted. Engaging is a case-participation decision, so the verb names the case rather than the report.

- **When…** a Participant accepts the case for further action
- **Send:** `Join(VulnerabilityCase)`
- **Sent by:** an active participant
- **How-to:** [How to Advance a Case Through Report Management](../../../../howto/activitypub/activities/manage_case.md)
- **Formal definition:** [Report/Case Accepted (RA)](../../../formal_protocol/messages.md#rm-message-types)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    engage_case,
    json2md,
)

print(json2md(engage_case()))
```
