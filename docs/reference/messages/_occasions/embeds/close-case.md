<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Close case"

    Leaves the case, moving the sender's RM state to Closed.

    - **When…** a Participant ends its participation in the case
    - **Send:** `Leave(VulnerabilityCase)`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the Case Owner or a participant
    - **Reference:** [Close case](../../case_management.md#close-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("close_case"))
        ```
