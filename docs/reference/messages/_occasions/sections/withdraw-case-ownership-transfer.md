<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Withdraw case ownership transfer { #withdraw-case-ownership-transfer }

Withdraws the ownership transfer offer before it is answered. The current Case Owner keeps the case.

- **When…** the Case Owner withdraws an open offer of case ownership
- **Send:** `Undo(Offer(VulnerabilityCase))`
- **Sent by:** the case owner
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    undo_case_ownership_transfer,
    json2md,
)

print(json2md(undo_case_ownership_transfer()))
```
