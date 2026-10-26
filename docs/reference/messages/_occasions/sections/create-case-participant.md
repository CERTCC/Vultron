<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Create case participant { #create-case-participant }

Carries the new participant record in full: its roles, statuses, joined mark and consent rows.

- **When…** the Case Manager creates a participant record, such as the inert record for the invitee of a stub Invite
- **Send:** `Create(CaseParticipant)`
- **Send to:** a participant
- **Sent by:** internal to the case manager
- **Mapping status:** [none](../../index.md#mapping-status)

Each participant learns of it from the case ledger, so it is addressed to nobody.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    create_participant,
    json2md,
)

print(json2md(create_participant()))
```
