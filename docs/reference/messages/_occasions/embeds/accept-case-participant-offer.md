<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Accept case participant offer"

    Accepts the proposed participant record. The CASE_MANAGER then invites the suggested actor.

    - **When…** the Case Owner approves a suggested actor
    - **Send:** `Accept(Offer(CaseParticipant)[target=VulnerabilityCase])`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the Case Owner
    - **Reference:** [Accept case participant offer](../../general.md#accept-case-participant-offer)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("accept_case_participant_offer"))
        ```
