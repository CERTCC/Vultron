<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Tentatively reject Full-Case Invite { #tentatively-reject-full-case-invite }

Tentatively rejects the Full-Case Invite, which records RM Invalid. It carries the sender's own ledger position.

- **When…** a Participant asked by a Full-Case Invite judges the case invalid
- **Send:** `TentativeReject(Invite(Actor)[target=VulnerabilityCase])`
- **Sent by:** the invitee
- **How-to:** [How to Invite an Actor to a Case](../../../../howto/activitypub/activities/invite_actor.md)
- **Formal definition:** [Report Invalid (RI)](../../../formal_protocol/messages.md#rm-message-types)
- **Mapping status:** [expansion](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    tentative_reject_full_case_invite,
    json2md,
)

print(json2md(tentative_reject_full_case_invite()))
```
