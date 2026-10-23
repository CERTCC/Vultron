<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Update case participant { #update-case-participant }

Carries the changed participant record in full, as the Case Manager stored it.

- **When…** the Case Manager changes a participant record, such as moving the CASE_OWNER role on an ownership transfer
- **Send:** `Update(CaseParticipant)`
- **Send to:** a participant
- **Sent by:** internal to the case manager
- **Mapping status:** [none](../../index.md#mapping-status)

Each participant learns of it from the case ledger, so it is addressed to nobody.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    update_participant,
    json2md,
)

print(json2md(update_participant()))
```
