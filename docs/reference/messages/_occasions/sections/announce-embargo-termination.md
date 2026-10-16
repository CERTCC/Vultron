<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Announce embargo termination { #announce-embargo-termination }

Tells the active participants other than the Case Manager that the embargo it names is terminated. It proposes nothing.

- **When…** the Case Manager has applied an Embargo Termination to the active embargo
- **Send:** `Announce(Event)[context=VulnerabilityCase]`
- **Send to:** a participant
- **Sent by:** the case manager
- **Seen in:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
- **Mapping status:** [none](../../index.md#mapping-status)

The wire form is the announcement of the embargo in force; the embargo it names, which the case's embargo register records as terminated, makes it a termination announcement.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    announce_embargo_termination,
    json2md,
)

print(json2md(announce_embargo_termination()))
```
