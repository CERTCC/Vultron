<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Embargo Revision Acceptance (EC) { #embargo-revision-acceptance }

Activates the revision for the case. It replaces the active embargo in the same register step.

=== "Details"

    - **When…** the Case Owner decides to replace the active embargo with a proposed revision
    - **Send:** `Add(EmbargoEvent)[target=VulnerabilityCase]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the Case Owner
    - **Distinguished by:** EM state `REVISE`
    - **Seen in:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
    - **Formal definition:** [Embargo Revision Acceptance (EC)](../../../formal_protocol/messages.md#em-message-types)
    - **Mapping status:** [collapse](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("activate_embargo_revision"))
    ```
