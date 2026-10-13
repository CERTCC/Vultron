<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Offer case ownership transfer"

    Offers the case to the actor named by the target, for example from a Reporter to a Coordinator. An `endTime`, when present, is the deadline to answer: the CASE_MANAGER refuses a later answer and records the offer as expired.

    - **When…** the Case Owner offers to transfer ownership of the case to another actor
    - **Send:** `Offer(VulnerabilityCase)`
    - **Sent by:** not yet checked
    - **Reference:** [Offer case ownership transfer](../../case_management.md#offer-case-ownership-transfer)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            offer_case_ownership_transfer,
            json2md,
        )

        print(json2md(offer_case_ownership_transfer()))
        ```
