<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Offer case participant role { #offer-case-participant-role }

Offers one role on the case to the actor named by the target.

- **When…** a Participant offers a CVD role on the case to another actor
- **Send:** `Offer(CaseParticipantRole)[context=VulnerabilityCase]`
- **Sent by:** not yet checked
- **How-to:** [How to Delegate a Role to Another Participant](../../../../howto/activitypub/activities/role_delegation.md)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    offer_case_participant_role,
    json2md,
)

print(json2md(offer_case_participant_role()))
```
