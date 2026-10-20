<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Ask the Case Manager to invite an actor { #request-invite-actor-to-case }

Asks the Case Manager to invite the actor named by the object to the case named by the target, with the roles in `suggestedRoles`. For an actor with no record on the case, or an invitee that has not answered, the Case Manager answers with the Stub Invite to that actor, not with an offer to the Case Owner.

- **When…** the Case Owner decides to invite an actor to the case
- **Send:** `Offer(Actor)[target=VulnerabilityCase]`
- **Send to:** the case manager
- **Sent by:** a participant (usually: case owner)
- **Distinguished by:** sender is the case owner
- **Seen in:** [How to Invite an Actor to a Case](../../../../howto/activitypub/activities/invite_actor.md)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    request_invite_actor_to_case,
    json2md,
)

print(json2md(request_invite_actor_to_case()))
```
