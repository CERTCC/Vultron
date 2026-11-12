<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Reject case ownership transfer"

    Declines the ownership transfer offer. The current Case Owner keeps the case.

    - **When…** an actor declines an offer of case ownership
    - **Send:** `Reject(Offer(VulnerabilityCase))`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the addressee of the vulnerability case offer
    - **Reference:** [Reject case ownership transfer](../../case_management.md#reject-case-ownership-transfer)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("reject_case_ownership_transfer"))
        ```
