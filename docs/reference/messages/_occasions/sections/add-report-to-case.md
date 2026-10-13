<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Add report to case { #add-report-to-case }

Adds a vulnerability report to the case named by the target.

- **When…** the Case Owner links a further report to an existing case
- **Send:** `Add(VulnerabilityReport)[target=VulnerabilityCase]`
- **Sent by:** the case owner
- **Seen in:** [How to Initialize a Case](../../../../howto/activitypub/activities/initialize_case.md)
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    add_report_to_case,
    json2md,
)

print(json2md(add_report_to_case()))
```
