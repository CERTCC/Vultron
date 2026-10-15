<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Accept case participant role { #accept-case-participant-role }

Accepts the offered role. The actor holds the role from then on.

- **When…** an actor accepts a role offered to it on the case
- **Send:** `Accept(Offer(CaseParticipantRole)[context=VulnerabilityCase])`
- **Send to:** a participant
- **Sent by:** not yet checked
- **Seen in:** [How to Delegate a Role to Another Participant](../../../../howto/activitypub/activities/role_delegation.md)
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    accept_case_participant_role,
    json2md,
)

print(json2md(accept_case_participant_role()))
```
