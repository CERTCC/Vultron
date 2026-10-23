<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Withdraw case ownership transfer"

    Withdraws the proposal, and with it the Case Manager's offer, before the offer is answered. The current Case Owner keeps the case.

    - **When…** the Case Owner withdraws its proposal while the offer of case ownership is open
    - **Send:** `Undo(Offer(Offer(VulnerabilityCase)))`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Reference:** [Withdraw case ownership transfer](../../case_management.md#withdraw-case-ownership-transfer)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            undo_case_ownership_transfer,
            json2md,
        )

        print(json2md(undo_case_ownership_transfer()))
        ```
