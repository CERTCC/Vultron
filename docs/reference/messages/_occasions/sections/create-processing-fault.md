<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Create processing fault { #create-processing-fault }

Tells the sender that its message was received but not understood. It names the failed activity and a failure class, with no implementation diagnostics. This fault serves the not-understood purpose of the formal RE, EE, CE and GE messages.

- **When…** a Participant has received a message it cannot process
- **Send:** `Create(ProcessingFault)`
- **Sent by:** not yet checked

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    create_processing_fault,
    json2md,
)

print(json2md(create_processing_fault()))
```
