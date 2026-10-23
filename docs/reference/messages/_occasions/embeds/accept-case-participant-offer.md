<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Accept case participant offer"

    Accepts the proposed participant record. The Case Manager then invites the suggested actor.

    - **When…** the Case Owner approves a suggested actor
    - **Send:** `Accept(Offer(CaseParticipant)[target=VulnerabilityCase])`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Reference:** [Accept case participant offer](../../general.md#accept-case-participant-offer)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            accept_case_participant_offer,
            json2md,
        )

        print(json2md(accept_case_participant_offer()))
        ```
