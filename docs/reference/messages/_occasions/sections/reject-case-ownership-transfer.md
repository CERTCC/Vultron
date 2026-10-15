<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Reject case ownership transfer { #reject-case-ownership-transfer }

Declines the ownership transfer offer. The current Case Owner keeps the case.

- **When…** an actor declines an offer of case ownership
- **Send:** `Reject(Offer(VulnerabilityCase))`
- **Send to:** the case manager
- **Sent by:** the addressee of the vulnerability case
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    reject_case_ownership_transfer,
    json2md,
)

print(json2md(reject_case_ownership_transfer()))
```
