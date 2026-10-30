<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Embargo Revision Acceptance (EC) { #embargo-revision-acceptance }

Activates the revision for the case. It replaces the active embargo in the same register step.

=== "Details"

    - **When…** the Case Owner decides to replace the active embargo with a proposed revision
    - **Send:** `Accept(EmbargoEvent)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Distinguished by:** EM state `REVISE`
    - **Seen in:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
    - **Formal definition:** [Embargo Revision Acceptance (EC)](../../../formal_protocol/messages.md#em-message-types)
    - **Mapping status:** [collapse](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        activate_embargo_revision,
        json2md,
    )

    print(json2md(activate_embargo_revision()))
    ```
