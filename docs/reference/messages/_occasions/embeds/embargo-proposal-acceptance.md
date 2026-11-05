<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Embargo Proposal Acceptance (EA)"

    Activates the proposal for the case. Any other open proposal stays open as a revision.

    - **When…** the Case Owner decides to activate a proposed embargo for a case with no active embargo
    - **Send:** `Accept(EmbargoEvent)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Distinguished by:** EM state `PROPOSED`
    - **Reference:** [Embargo Proposal Acceptance (EA)](../../em.md#embargo-proposal-acceptance)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            activate_embargo,
            json2md,
        )

        print(json2md(activate_embargo()))
        ```
