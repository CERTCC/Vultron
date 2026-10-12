<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Reject Full-Case Invite { #reject-full-case-invite }

Rejects the Full-Case Invite, which records RM Closed. It carries the sender's own ledger position.

- **When…** a Participant asked by a Full-Case Invite closes the case
- **Send:** `Reject(Invite(Actor)[target=VulnerabilityCase])`
- **Sent by:** the invitee
- **How-to:** [How to Invite an Actor to a Case](../../../../howto/activitypub/activities/invite_actor.md)
- **Formal definition:** [Report Closed (RC)](../../../formal_protocol/messages.md#rm-message-types)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    reject_full_case_invite,
    json2md,
)

print(json2md(reject_full_case_invite()))
```
