<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Fix Readiness (CF)"

    Announces that the Vendor whose participant record is the target has a fix ready.

    - **When…** a Vendor has a fix ready
    - **Send:** `Add(ParticipantStatus)[target=CaseParticipant]`
    - **Sent by:** a participant (usually: vendor)
    - **Distinguished by:** `vfState` = `VF`
    - **Reference:** [Fix Readiness (CF)](../../cs.md#fix-readiness)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            add_fix_readiness_to_participant,
            json2md,
        )

        print(json2md(add_fix_readiness_to_participant()))
        ```
