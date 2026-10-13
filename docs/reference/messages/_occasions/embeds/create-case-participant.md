<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Create case participant"

    Mints a participant record that pairs an actor with its roles in the case. It precedes the Add.

    - **When…** a Participant is about to add an actor's participant record to the case
    - **Send:** `Create(CaseParticipant)[context=VulnerabilityCase]`
    - **Sent by:** not yet checked
    - **Reference:** [Create case participant](../../case_management.md#create-case-participant)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            create_participant,
            json2md,
        )

        print(json2md(create_participant()))
        ```
