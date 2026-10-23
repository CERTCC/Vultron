<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Embargo Revision Acceptance (EC) { #embargo-revision-acceptance }

Records the sender's own consent to the revision. The revision replaces the active embargo only when the Case Owner sends its decision.

- **When…** a Participant agrees to a proposed embargo revision
- **Send:** `Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])`
- **Send to:** the case manager
- **Sent by:** the invitee
- **Distinguished by:** EM state `REVISE`
- **Seen in:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
- **Formal definition:** [Embargo Revision Acceptance (EC)](../../../formal_protocol/messages.md#em-message-types)
- **Mapping status:** [collapse](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    accept_embargo_revision,
    json2md,
)

print(json2md(accept_embargo_revision()))
```
