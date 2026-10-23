<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Accept case proposal { #accept-case-proposal }

Accepts the case proposal and tells the proposing actor that a case will be opened for its report.

- **When…** a Case Actor Service agrees to open the proposed case
- **Send:** `Accept(CaseProposal)`
- **Send to:** an actor outside any case
- **Sent by:** the addressee of the case proposal
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    accept_case_proposal,
    json2md,
)

print(json2md(accept_case_proposal()))
```
