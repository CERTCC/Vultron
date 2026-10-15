<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Invalidate report { #report-invalid }

Designates the report as invalid, moving the sender's RM state to Invalid.

- **When…** a report receiver judges the report invalid
- **Send:** `TentativeReject(Offer(VulnerabilityReport))`
- **Send to:** the case manager
- **Sent by:** a participant (usually: vendor, coordinator)
- **Seen in:** [How to Report a Vulnerability](../../../../howto/activitypub/activities/report_vulnerability.md)
- **Formal definition:** [Report Invalid (RI)](../../../formal_protocol/messages.md#rm-message-types)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    invalidate_report,
    json2md,
)

print(json2md(invalidate_report()))
```
