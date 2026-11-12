<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Embargo Termination (ET) { #embargo-termination }

Terminates the embargo with immediate effect.

=== "Details"

    - **When…** the Case Owner terminates the active embargo
    - **Send:** `Remove(EmbargoEvent)`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the CASE_MANAGER or the Case Owner
    - **Seen in:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
    - **Formal definition:** [Embargo Termination (ET)](../../../formal_protocol/messages.md#em-message-types)
    - **Mapping status:** [direct](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("remove_embargo"))
    ```
