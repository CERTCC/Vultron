<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Close report { #report-closed }

Closes the report, moving the sender's RM state to Closed.

- **When…** a report receiver closes the report
- **Send:** `Reject(Offer(VulnerabilityReport))`
- **Sent by:** an active participant (usually: vendor, coordinator)
- **How-to:** [How to Report a Vulnerability](../../../../howto/activitypub/activities/report_vulnerability.md)
- **Formal definition:** [Report Closed (RC)](../../../formal_protocol/messages.md#rm-message-types)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    close_report,
    json2md,
)

print(json2md(close_report()))
```
