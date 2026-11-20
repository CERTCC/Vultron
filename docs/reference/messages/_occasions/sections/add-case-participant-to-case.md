<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Add case participant to case { #add-case-participant-to-case }

Carries the new participant record in full: its roles, statuses, joined mark and consent rows. The target is the case whose participant list the record joins.

=== "Details"

    - **When…** the CASE_MANAGER adds a new participant record to the case, such as the inert record for the invitee of a stub Invite
    - **Send:** `Add(CaseParticipant)[target=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** internal to the CASE_MANAGER
    - **Mapping status:** [none](../../index.md#mapping-status)

    Each participant learns of it from the case ledger, so it is addressed to nobody.

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("add_participant_to_case"))
    ```
