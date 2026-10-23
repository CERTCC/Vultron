<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Offer case participant role"

    Offers one role on the case to the participant named by the target. The Case Manager records the offer and forwards it to that participant.

    - **When…** the Case Owner offers a CVD role on the case to another participant
    - **Send:** `Offer(CaseParticipantRole)[context=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Reference:** [Offer case participant role](../../case_management.md#offer-case-participant-role)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            offer_case_participant_role,
            json2md,
        )

        print(json2md(offer_case_participant_role()))
        ```
