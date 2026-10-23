<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Create case participant"

    Carries the new participant record in full: its roles, statuses, joined mark and consent rows.

    - **When…** the Case Manager creates a participant record, such as the inert record for the invitee of a stub Invite
    - **Send:** `Create(CaseParticipant)`
    - **Send to:** a participant
    - **Sent by:** internal to the case manager
    - **Reference:** [Create case participant](../../case_management.md#create-case-participant)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            create_participant,
            json2md,
        )

        print(json2md(create_participant()))
        ```
