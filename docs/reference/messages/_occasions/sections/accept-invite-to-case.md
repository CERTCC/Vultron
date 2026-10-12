<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Accept invite to case { #accept-invite-to-case }

Accepts the Stub Invite. The actor joins the case at RM Received.

- **When…** an invited actor agrees to join the case
- **Send:** `Accept(Invite(Actor)[target=VulnerabilityCaseStub])`
- **Sent by:** the invitee
- **How-to:** [How to Invite an Actor to a Case](../../../../howto/activitypub/activities/invite_actor.md)
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    accept_invite_to_case,
    json2md,
)

print(json2md(accept_invite_to_case()))
```
