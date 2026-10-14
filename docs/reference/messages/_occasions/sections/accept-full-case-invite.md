<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Accept Full-Case Invite { #accept-full-case-invite }

Accepts the Full-Case Invite, which records RM Valid. It carries the sender's own ledger position.

- **When…** a Participant asked by a Full-Case Invite judges the case valid
- **Send:** `Accept(Invite(Actor)[target=VulnerabilityCase])`
- **Sent by:** the invitee
- **Seen in:** [How to Manage a Case Roster](../../../../howto/activitypub/activities/manage_participants.md)
- **Formal definition:** [Report Valid (RV)](../../../formal_protocol/messages.md#rm-message-types)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    accept_full_case_invite,
    json2md,
)

print(json2md(accept_full_case_invite()))
```
