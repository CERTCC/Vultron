<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Update case { #update-case }

Sends the changed case object, for example after a title edit or an applied ownership transfer.

- **When…** the Case Manager has recorded a change to the case object
- **Send:** `Update(VulnerabilityCase)`
- **Sent by:** not yet checked

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    update_case,
    json2md,
)

print(json2md(update_case()))
```
