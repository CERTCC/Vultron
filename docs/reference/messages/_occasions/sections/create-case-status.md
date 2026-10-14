<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Create case status { #create-case-status }

Mints a case status object carrying `em_state` and `pxa_state`. It precedes the Add.

- **When…** a Participant is about to announce a change to the public state of the case
- **Send:** `Create(CaseStatus)[context=VulnerabilityCase]`
- **Sent by:** not yet checked
- **Seen in:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    create_case_status,
    json2md,
)

print(json2md(create_case_status()))
```
