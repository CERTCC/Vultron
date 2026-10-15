<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Accept case ownership transfer"

    Accepts the ownership transfer offer.

    - **When…** an actor accepts an offer of case ownership
    - **Send:** `Accept(Offer(VulnerabilityCase))`
    - **Send to:** the case manager
    - **Sent by:** the addressee of the vulnerability case
    - **Reference:** [Accept case ownership transfer](../../case_management.md#accept-case-ownership-transfer)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            accept_case_ownership_transfer,
            json2md,
        )

        print(json2md(accept_case_ownership_transfer()))
        ```
