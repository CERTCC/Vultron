<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Remove case participant from case { #remove-case-participant-from-case }

Asks the Case Manager to remove the participant record named by the object. The removed Participant receives a direct notice.

- **When…** the Case Owner removes a Participant from active participation
- **Send:** `Remove(CaseParticipant)[target=VulnerabilityCase]`
- **Sent by:** the case owner
- **How-to:** [How to Manage a Case Roster](../../../../howto/activitypub/activities/manage_participants.md)
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    remove_participant_from_case,
    json2md,
)

print(json2md(remove_participant_from_case()))
```
