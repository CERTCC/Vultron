<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Activate embargo"

    Activates the proposal for the case. If an embargo is already active, the proposal replaces it.

    - **When…** the Case Owner decides to activate a proposed embargo
    - **Send:** `Accept(EmbargoEvent)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Reference:** [Activate embargo](../../em.md#activate-embargo)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            activate_embargo,
            json2md,
        )

        print(json2md(activate_embargo()))
        ```
