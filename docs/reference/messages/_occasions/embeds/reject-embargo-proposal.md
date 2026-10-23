<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Reject embargo proposal"

    Rejects the proposal for the case. An active embargo stays in force on its current terms.

    - **When…** the Case Owner decides to reject a proposed embargo
    - **Send:** `Reject(EmbargoEvent)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Reference:** [Reject embargo proposal](../../em.md#reject-embargo-proposal)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            reject_embargo_proposal,
            json2md,
        )

        print(json2md(reject_embargo_proposal()))
        ```
