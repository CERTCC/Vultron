<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Reject case participant offer"

    Rejects the proposed participant record. The Case Manager tells the recommender.

    - **When…** the Case Owner declines a suggested actor
    - **Send:** `Reject(Offer(CaseParticipant)[target=VulnerabilityCase])`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Reference:** [Reject case participant offer](../../general.md#reject-case-participant-offer)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            reject_case_participant_offer,
            json2md,
        )

        print(json2md(reject_case_participant_offer()))
        ```
