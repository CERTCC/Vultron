<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Close case"

    Leaves the case, moving the sender's RM state to Closed.

    - **When…** a Participant ends its participation in the case
    - **Send:** `Leave(VulnerabilityCase)`
    - **Send to:** the case manager
    - **Sent by:** the case owner or a participant
    - **Reference:** [Close case](../../case_management.md#close-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            close_case,
            json2md,
        )

        print(json2md(close_case()))
        ```
