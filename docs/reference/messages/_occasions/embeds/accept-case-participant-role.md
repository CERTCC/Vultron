<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Accept case participant role"

    Accepts the offered role. The actor holds the role from then on.

    - **When…** an actor accepts a role offered to it on the case
    - **Send:** `Accept(Offer(CaseParticipantRole)[context=VulnerabilityCase])`
    - **Sent by:** not yet checked
    - **Reference:** [Accept case participant role](../../case_management.md#accept-case-participant-role)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            accept_case_participant_role,
            json2md,
        )

        print(json2md(accept_case_participant_role()))
        ```
