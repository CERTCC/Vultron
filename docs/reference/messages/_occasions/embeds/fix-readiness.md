<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Fix Readiness (CF)"

    Announces that the Vendor whose participant record is the target has a fix ready.

    - **When…** a Vendor has a fix ready
    - **Send:** `Add(ParticipantStatus)[target=CaseParticipant]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the CASE_MANAGER or the Case Owner or the participant status's author (usually: vendor)
    - **Distinguished by:** `vfState` = `VF`
    - **Reference:** [Fix Readiness (CF)](../../cs.md#fix-readiness)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("add_fix_readiness_to_participant"))
        ```
