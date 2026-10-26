<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Tell a participant the embargo has ended { #embargo-termination-notice }

Tells one participant that the embargo has ended, with immediate effect. The Case Manager sends one to each participant other than itself, naming the Case Owner in `attributedTo` when the Case Owner asked for the termination.

- **When…** the Case Manager ends the active embargo, on its own decision or on the Case Owner's
- **Send:** `Remove(EmbargoEvent)`
- **Send to:** a participant
- **Sent by:** the case manager
- **Seen in:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
- **Mapping status:** [direct](../../index.md#mapping-status)

The wire form is the Embargo Termination (ET) a Case Owner sends; only its sender and addressee differ.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    notify_embargo_termination,
    json2md,
)

print(json2md(notify_embargo_termination()))
```
