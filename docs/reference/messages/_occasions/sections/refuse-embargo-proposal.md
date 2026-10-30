<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Refuse proposed embargo terms { #refuse-embargo-proposal }

Records the sender's own refusal of the proposed terms. The proposal is rejected for the case only when the Case Owner sends its decision.

=== "Details"

    - **When…** a Participant refuses proposed embargo terms
    - **Send:** `Reject(Invite(EmbargoEvent)[context=VulnerabilityCase])`
    - **Send to:** the case manager
    - **Sent by:** the invitee
    - **Distinguished by:** EM state `PROPOSED`
    - **Seen in:** [How to Establish an Embargo](../../../../howto/activitypub/activities/establish_embargo.md)
    - **Mapping status:** [expansion](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        reject_embargo,
        json2md,
    )

    print(json2md(reject_embargo()))
    ```
