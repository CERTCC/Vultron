<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Reject case proposal { #reject-case-proposal }

Rejects the case proposal. No case is opened.

- **When…** a Case Actor Service declines to open the proposed case
- **Send:** `Reject(CaseProposal)`
- **Send to:** an actor outside any case
- **Sent by:** the addressee of the case proposal
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    reject_case_proposal,
    json2md,
)

print(json2md(reject_case_proposal()))
```
