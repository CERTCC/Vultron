<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Attacks observed in a participant status { #participant-attacks-observed }

Announces, in the sender's own participant status, evidence that attackers are exploiting the vulnerability.

- **When…** a Participant observes attacks that exploit the vulnerability
- **Send:** `Add(ParticipantStatus)[target=CaseParticipant]`
- **Send to:** the case manager
- **Sent by:** a participant
- **Distinguished by:** `caseStatus.pxaState` = `pxA`
- **Seen in:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
- **Formal definition:** [Attacks Observed (CA)](../../../formal_protocol/messages.md#cs-message-types)
- **Mapping status:** [collapse](../../index.md#mapping-status)

A participant status is a snapshot of every dimension the sender holds, so it can also carry an unchanged `vfState` or `dState`; the dimension that changed makes the occasion. The report is the sender's view of the case status, not a change to it. The Case Manager records the status on the sender's participant record and chooses whether to adopt the reported `pxaState` for the case, by default only with the Case Owner's authorization. Only an adopted value changes the case status, and while an embargo is active or proposed, it ends or abandons the embargo.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    add_attacks_observed_to_participant,
    json2md,
)

print(json2md(add_attacks_observed_to_participant()))
```
