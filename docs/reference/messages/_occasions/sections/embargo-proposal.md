<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Embargo Proposal (EP) { #embargo-proposal }

Proposes embargo terms, such as an end date and time.

- **When…** a Participant proposes embargo terms for a case with no active embargo
- **Send:** `Invite(Event)[context=VulnerabilityCase]`
- **Send to:** the case manager
- **Sent by:** the case manager or an active participant
- **Distinguished by:** EM state `NONE` or `PROPOSED`
- **Seen in:** [How to Establish an Embargo](../../../../howto/activitypub/activities/establish_embargo.md)
- **Formal definition:** [Embargo Proposal (EP)](../../../formal_protocol/messages.md#em-message-types)
- **Mapping status:** [collapse](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    propose_embargo,
    json2md,
)

print(json2md(propose_embargo()))
```
