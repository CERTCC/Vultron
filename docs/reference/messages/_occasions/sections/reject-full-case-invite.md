<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Reject Full-Case Invite { #reject-full-case-invite }

Rejects the Full-Case Invite, which records RM Closed. It carries the sender's own ledger position.

- **When…** a Participant asked by a Full-Case Invite closes the case
- **Send:** `Reject(Invite(Actor)[target=VulnerabilityCase])`
- **Send to:** the case manager
- **Sent by:** the invitee
- **Seen in:** [How to Manage a Case Roster](../../../../howto/activitypub/activities/manage_participants.md)
- **Formal definition:** [Report Closed (RC)](../../../formal_protocol/messages.md#rm-message-types)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    reject_full_case_invite,
    json2md,
)

print(json2md(reject_full_case_invite()))
```
