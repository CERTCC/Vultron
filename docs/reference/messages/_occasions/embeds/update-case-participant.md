<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Update case participant"

    Carries the changed participant record in full, as the Case Manager stored it.

    - **When…** the Case Manager changes a participant record, such as moving the CASE_OWNER role on an ownership transfer
    - **Send:** `Update(CaseParticipant)`
    - **Send to:** a participant
    - **Sent by:** not handled
    - **Reference:** [Update case participant](../../case_management.md#update-case-participant)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            update_participant,
            json2md,
        )

        print(json2md(update_participant()))
        ```
