<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Agree to proposed embargo terms { #agree-to-embargo-proposal }

Records the sender's own consent to the proposed terms. The embargo becomes active only when the Case Owner sends its decision.

=== "Details"

    - **When…** a Participant agrees to proposed embargo terms
    - **Send:** `Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])`
    - **Send to:** the case manager
    - **Sent by:** the invitee
    - **Distinguished by:** EM state `PROPOSED`
    - **Seen in:** [How to Establish an Embargo](../../../../howto/activitypub/activities/establish_embargo.md)
    - **Mapping status:** [none](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        accept_embargo,
        json2md,
    )

    print(json2md(accept_embargo()))
    ```
