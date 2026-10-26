<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Embargo Revision Rejection (EJ) { #embargo-revision-rejection }

Records the sender's own refusal of the revision. The Case Owner keeps the prior terms by sending its decision.

=== "Details"

    - **When…** a Participant refuses a proposed embargo revision
    - **Send:** `Reject(Invite(EmbargoEvent)[context=VulnerabilityCase])`
    - **Send to:** the case manager
    - **Sent by:** the invitee
    - **Distinguished by:** EM state `REVISE`
    - **Seen in:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
    - **Formal definition:** [Embargo Revision Rejection (EJ)](../../../formal_protocol/messages.md#em-message-types)
    - **Mapping status:** [collapse](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        reject_embargo_revision,
        json2md,
    )

    print(json2md(reject_embargo_revision()))
    ```
