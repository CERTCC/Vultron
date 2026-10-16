<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Public awareness in a participant status"

    Announces, in the sender's own participant status, evidence that the vulnerability is known to the public.

    - **When…** a Participant learns that the public knows of the vulnerability
    - **Send:** `Add(ParticipantStatus)[target=CaseParticipant]`
    - **Send to:** the case manager
    - **Sent by:** a participant
    - **Distinguished by:** `caseStatus.pxaState` = `Pxa`
    - **Reference:** [Public awareness in a participant status](../../cs.md#participant-public-awareness)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            add_public_awareness_to_participant,
            json2md,
        )

        print(json2md(add_public_awareness_to_participant()))
        ```
