<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Ask a participant about proposed embargo terms { #relay-embargo-proposal }

Asks one participant to accept or reject proposed embargo terms, or a proposed revision. The Case Manager sends one to each participant other than the proposer, naming the proposer in `attributedTo`, and the participant's answer names this Invite.

- **When…** the Case Manager asks a Participant to answer embargo terms another Participant proposed
- **Send:** `Invite(Event)[context=VulnerabilityCase]`
- **Send to:** a participant
- **Sent by:** the case manager
- **Seen in:** [How to Establish an Embargo](../../../../howto/activitypub/activities/establish_embargo.md)
- **Mapping status:** [collapse](../../index.md#mapping-status)

The wire form is the Embargo Proposal (EP) or Embargo Revision Proposal (EV) a participant sends; only its sender and addressee differ.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    relay_embargo_proposal,
    json2md,
)

print(json2md(relay_embargo_proposal()))
```
