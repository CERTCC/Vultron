<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Create report { #create-report }

Mints the vulnerability report object. It precedes the Offer that submits the report.

- **When…** a Reporter has written up a vulnerability and is about to submit the report
- **Send:** `Create(VulnerabilityReport)`
- **Send to:** an actor outside any case
- **Sent by:** any actor (usually: finder, reporter)
- **Seen in:** [How to Report a Vulnerability](../../../../howto/activitypub/activities/report_vulnerability.md)
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    create_report,
    json2md,
)

print(json2md(create_report()))
```
