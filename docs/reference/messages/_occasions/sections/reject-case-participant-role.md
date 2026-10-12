<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Reject case participant role { #reject-case-participant-role }

Declines the offered role. The roster does not change.

- **When…** an actor declines a role offered to it on the case
- **Send:** `Reject(Offer(CaseParticipantRole)[context=VulnerabilityCase])`
- **Sent by:** not yet checked
- **How-to:** [How to Delegate a Role to Another Participant](../../../../howto/activitypub/activities/role_delegation.md)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    reject_case_participant_role,
    json2md,
)

print(json2md(reject_case_participant_role()))
```
