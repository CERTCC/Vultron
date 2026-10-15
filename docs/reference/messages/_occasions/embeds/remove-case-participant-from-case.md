<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Remove case participant from case"

    Asks the Case Manager to remove the participant record named by the object. The removed Participant receives a direct notice.

    - **When…** the Case Owner removes a Participant from active participation
    - **Send:** `Remove(CaseParticipant)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Reference:** [Remove case participant from case](../../case_management.md#remove-case-participant-from-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            remove_participant_from_case,
            json2md,
        )

        print(json2md(remove_participant_from_case()))
        ```
