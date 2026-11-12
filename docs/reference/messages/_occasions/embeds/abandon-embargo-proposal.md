<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Abandon embargo proposal"

    Cancels the proposal for the case. The CASE_MANAGER then withdraws each Invite it relayed for the proposal. This Reject is not the CASE_MANAGER's consent.

    - **When…** the CASE_MANAGER abandons an open embargo proposal it received once the case is public, an exploit is public or attacks are observed
    - **Send:** `Reject(Invite(EmbargoEvent)[context=VulnerabilityCase])`
    - **Send to:** a participant
    - **Sent by:** the CASE_MANAGER
    - **Reference:** [Abandon embargo proposal](../../em.md#abandon-embargo-proposal)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("abandon_embargo_proposal"))
        ```
