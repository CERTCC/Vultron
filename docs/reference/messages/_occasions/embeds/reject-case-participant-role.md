<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Reject case participant role"

    Declines the offered role. The roster does not change.

    - **When…** an actor declines a role offered to it on the case
    - **Send:** `Reject(Offer(CaseParticipantRole)[context=VulnerabilityCase])`
    - **Sent by:** not yet checked
    - **Reference:** [Reject case participant role](../../case_management.md#reject-case-participant-role)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            reject_case_participant_role,
            json2md,
        )

        print(json2md(reject_case_participant_role()))
        ```
