<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Report Submission (RS) { #report-submission }

Offers the report to a new Participant. The Offer may carry proposed embargo terms.

- **When…** a Reporter submits a vulnerability report to a Vendor or Coordinator
- **Send:** `Offer(VulnerabilityReport)`
- **Sent by:** any actor (usually: reporter)
- **How-to:** [How to Report a Vulnerability](../../../../howto/activitypub/activities/report_vulnerability.md)
- **Formal definition:** [Report Submission (RS)](../../../formal_protocol/messages.md#rm-message-types)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    submit_report,
    json2md,
)

print(json2md(submit_report()))
```
