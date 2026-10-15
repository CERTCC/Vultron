<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Offer case ownership transfer { #offer-case-ownership-transfer }

Offers the case to the actor named by the target, for example from a Reporter to a Coordinator, optionally with an `endTime` after which the CASE_MANAGER refuses an answer and records the offer as expired.

- **When…** the Case Owner offers to transfer ownership of the case to another actor
- **Send:** `Offer(VulnerabilityCase)`
- **Send to:** the case manager
- **Sent by:** not yet checked
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    offer_case_ownership_transfer,
    json2md,
)

print(json2md(offer_case_ownership_transfer()))
```
