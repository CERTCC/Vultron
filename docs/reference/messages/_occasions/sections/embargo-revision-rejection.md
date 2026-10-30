<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Embargo Revision Rejection (EJ) { #embargo-revision-rejection }

Rejects the revision for the case. The active embargo stays in force on its prior terms, unless the case is public, an exploit is public or attacks are observed, when the Case Manager also ends it.

=== "Details"

    - **When…** the Case Owner decides to reject a proposed revision
    - **Send:** `Reject(EmbargoEvent)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Distinguished by:** EM state `REVISE`
    - **Seen in:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
    - **Formal definition:** [Embargo Revision Rejection (EJ)](../../../formal_protocol/messages.md#em-message-types)
    - **Mapping status:** [collapse](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        reject_embargo_revision_proposal,
        json2md,
    )

    print(json2md(reject_embargo_revision_proposal()))
    ```
