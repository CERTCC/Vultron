<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Accept Full-Case Invite { #accept-full-case-invite }

Accepts the Full-Case Invite, which records RM Valid. It carries the sender's own ledger position.

- **When…** a Participant asked by a Full-Case Invite judges the case valid
- **Send:** `Accept(Invite(Actor)[target=VulnerabilityCase])`
- **Sent by:** the invitee
- **How-to:** [How to Invite an Actor to a Case](../../../../howto/activitypub/activities/invite_actor.md)
- **Formal definition:** [Report Valid (RV)](../../../formal_protocol/messages.md#rm-message-types)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    accept_full_case_invite,
    json2md,
)

print(json2md(accept_full_case_invite()))
```
