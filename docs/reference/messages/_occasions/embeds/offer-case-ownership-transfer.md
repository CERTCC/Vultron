<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Offer case ownership transfer"

    Offers the case to the actor named by the target, on the Case Owner's behalf: `attributedTo` names the owner. This is the one offer of the transfer, the one the new owner accepts or rejects. It carries the proposal's `endTime`, if any.

    - **When…** the Case Manager offers the case to the actor the Case Owner proposed
    - **Send:** `Offer(VulnerabilityCase)`
    - **Send to:** a participant
    - **Sent by:** the case manager
    - **Reference:** [Offer case ownership transfer](../../case_management.md#offer-case-ownership-transfer)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            offer_case_ownership_transfer,
            json2md,
        )

        print(json2md(offer_case_ownership_transfer()))
        ```
