<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Add case participant to case"

    Asks the Case Manager to reinstate the participant record named by the object. The Participant becomes active again and receives the ledger entries it missed.

    - **When…** the Case Owner reinstates a removed Participant
    - **Send:** `Add(CaseParticipant)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Reference:** [Add case participant to case](../../case_management.md#add-case-participant-to-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            add_coordinator_participant_to_case,
            json2md,
        )

        print(json2md(add_coordinator_participant_to_case()))
        ```
