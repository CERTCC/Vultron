<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Invite actor to case { #invite-actor-to-case }

Sends a Stub Invite carrying the case stub and the embargo terms the invitee would agree to.

- **When…** the Case Manager invites an actor to join the case
- **Send:** `Invite(Actor)[target=VulnerabilityCaseStub]`
- **Send to:** a participant
- **Sent by:** the case manager
- **Seen in:** [How to Seat a Participant on an Existing Case](../../../../howto/activitypub/activities/initialize_participant.md), [How to Invite an Actor to a Case](../../../../howto/activitypub/activities/invite_actor.md)
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    rm_invite_to_case,
    json2md,
)

print(json2md(rm_invite_to_case()))
```
