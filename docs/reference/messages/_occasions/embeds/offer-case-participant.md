<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Offer case participant"

    Forwards the recommendation as a proposed participant record, carrying the original recommendation's ID and the default roles it assigned.

    - **When…** the Case Manager presents a suggested actor to the Case Owner
    - **Send:** `Offer(CaseParticipant)[target=VulnerabilityCase]`
    - **Sent by:** the case manager
    - **Reference:** [Offer case participant](../../general.md#offer-case-participant)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            offer_case_participant,
            json2md,
        )

        print(json2md(offer_case_participant()))
        ```
