<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Reject invite to case { #reject-invite-to-case }

Rejects the Stub Invite, which closes the invitee's participant record.

- **When…** an invited actor declines to join the case
- **Send:** `Reject(Invite(Actor)[target=VulnerabilityCaseStub])`
- **Sent by:** the invitee
- **How-to:** [How to Invite an Actor to a Case](../../../../howto/activitypub/activities/invite_actor.md)
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    reject_invite_to_case,
    json2md,
)

print(json2md(reject_invite_to_case()))
```
