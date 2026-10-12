<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Create participant status { #create-participant-status }

Mints a participant status object carrying `rm_state`, `vf_state` and `d_state`. It precedes the Add.

- **When…** a Participant is about to announce a change to its own state in the case
- **Send:** `Create(ParticipantStatus)`
- **Sent by:** not yet checked
- **How-to:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    create_participant_status,
    json2md,
)

print(json2md(create_participant_status()))
```
