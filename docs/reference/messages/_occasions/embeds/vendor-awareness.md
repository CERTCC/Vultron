<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Vendor Awareness (CV)"

    Announces that the report has reached the Vendor whose participant record is the target.

    - **When…** a Vendor becomes aware of the vulnerability
    - **Send:** `Add(ParticipantStatus)[target=CaseParticipant]`
    - **Sent by:** an active participant (usually: vendor)
    - **Distinguished by:** `vf_state` = `Vf`
    - **Reference:** [Vendor Awareness (CV)](../../cs.md#vendor-awareness)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            add_vendor_awareness_to_participant,
            json2md,
        )

        print(json2md(add_vendor_awareness_to_participant()))
        ```
