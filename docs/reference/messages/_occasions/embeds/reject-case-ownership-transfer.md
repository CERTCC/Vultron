<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Reject case ownership transfer"

    Declines the ownership transfer offer. The current Case Owner keeps the case.

    - **When…** an actor declines an offer of case ownership
    - **Send:** `Reject(Offer(VulnerabilityCase))`
    - **Sent by:** the addressee of the vulnerability case
    - **Reference:** [Reject case ownership transfer](../../case_management.md#reject-case-ownership-transfer)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            reject_case_ownership_transfer,
            json2md,
        )

        print(json2md(reject_case_ownership_transfer()))
        ```
