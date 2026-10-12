<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Embargo Revision Proposal (EV) { #embargo-revision-proposal }

Proposes a revision to the terms of the active embargo. The wire form is the same as a first proposal; the receiver's EM state makes it a revision.

- **When…** a Participant proposes revised terms for the active embargo
- **Send:** `Invite(Event)[context=VulnerabilityCase]`
- **Sent by:** an active participant
- **Distinguished by:** EM state `ACTIVE` or `REVISE`
- **How-to:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
- **Formal definition:** [Embargo Revision Proposal (EV)](../../../formal_protocol/messages.md#em-message-types)
- **Mapping status:** [collapse](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    propose_embargo_revision,
    json2md,
)

print(json2md(propose_embargo_revision()))
```
