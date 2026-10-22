<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Update case owner { #update-case-owner }

Carries the case with its new owner in attributedTo. The Case Manager commits it after the Accept of the transfer and after each participant record whose CASE_OWNER role moved.

- **When…** the Case Manager records the new Case Owner once a case ownership transfer is accepted
- **Send:** `Update(VulnerabilityCase)`
- **Send to:** a participant
- **Sent by:** not handled
- **Mapping status:** [none](../../index.md#mapping-status)

Each participant learns of it from the case ledger, so it is addressed to nobody.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    update_case,
    json2md,
)

print(json2md(update_case()))
```
