<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Attacks observed in a participant status"

    Announces, in the sender's own participant status, evidence that attackers are exploiting the vulnerability.

    - **When…** a Participant observes attacks that exploit the vulnerability
    - **Send:** `Add(ParticipantStatus)[target=CaseParticipant]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the CASE_MANAGER or the Case Owner or the participant status's author
    - **Distinguished by:** `caseStatus.pxaState` = `pxA`
    - **Reference:** [Attacks observed in a participant status](../../cs.md#participant-attacks-observed)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("add_attacks_observed_to_participant"))
        ```
