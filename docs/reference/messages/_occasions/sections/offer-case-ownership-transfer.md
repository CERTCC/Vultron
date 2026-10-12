<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Offer case ownership transfer { #offer-case-ownership-transfer }

Offers the case to the actor named by the target, for example from a Reporter to a Coordinator.

- **When…** the Case Owner offers to transfer ownership of the case to another actor
- **Send:** `Offer(VulnerabilityCase)`
- **Sent by:** not yet checked

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    offer_case_ownership_transfer,
    json2md,
)

print(json2md(offer_case_ownership_transfer()))
```
