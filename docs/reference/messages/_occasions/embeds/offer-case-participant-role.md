<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Offer case participant role"

    Offers one role on the case to the actor named by the target.

    - **When…** a Participant offers a CVD role on the case to another actor
    - **Send:** `Offer(CaseParticipantRole)[context=VulnerabilityCase]`
    - **Sent by:** not yet checked
    - **Reference:** [Offer case participant role](../../case_management.md#offer-case-participant-role)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            offer_case_participant_role,
            json2md,
        )

        print(json2md(offer_case_participant_role()))
        ```
