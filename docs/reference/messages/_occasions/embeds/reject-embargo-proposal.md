<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Reject embargo proposal"

    Rejects the proposal for the case. The case has no embargo once no other proposal is open.

    - **When…** the Case Owner decides to reject a proposed embargo for a case with no active embargo
    - **Send:** `Reject(EmbargoEvent)[target=VulnerabilityCase]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the Case Owner
    - **Distinguished by:** EM state `PROPOSED`
    - **Reference:** [Reject embargo proposal](../../em.md#reject-embargo-proposal)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("reject_embargo_proposal"))
        ```
