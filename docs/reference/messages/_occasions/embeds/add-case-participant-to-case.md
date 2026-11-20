<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Add case participant to case"

    Carries the new participant record in full: its roles, statuses, joined mark and consent rows. The target is the case whose participant list the record joins.

    - **When…** the CASE_MANAGER adds a new participant record to the case, such as the inert record for the invitee of a stub Invite
    - **Send:** `Add(CaseParticipant)[target=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** internal to the CASE_MANAGER
    - **Reference:** [Add case participant to case](../../case_management.md#add-case-participant-to-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("add_participant_to_case"))
        ```
