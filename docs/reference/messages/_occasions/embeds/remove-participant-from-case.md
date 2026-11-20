<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Remove participant from case"

    The Case Owner's own removal of the actor named by the object, from the case named by the origin. The CASE_MANAGER records it as the ledger entry and announces it to the removed actor.

    - **When…** the Case Owner removes a Participant from active participation
    - **Send:** `Remove(Actor)[origin=VulnerabilityCase]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the Case Owner
    - **Reference:** [Remove participant from case](../../case_management.md#remove-participant-from-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("remove_participant_from_case"))
        ```
