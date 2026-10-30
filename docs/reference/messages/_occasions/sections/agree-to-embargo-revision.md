<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Agree to an embargo revision { #agree-to-embargo-revision }

Records the sender's own consent to the revision. The revision replaces the active embargo only when the Case Owner sends its decision.

=== "Details"

    - **When…** a Participant agrees to a proposed embargo revision
    - **Send:** `Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])`
    - **Send to:** the case manager
    - **Sent by:** the invitee
    - **Distinguished by:** EM state `REVISE`
    - **Seen in:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
    - **Mapping status:** [none](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        accept_embargo_revision,
        json2md,
    )

    print(json2md(accept_embargo_revision()))
    ```
