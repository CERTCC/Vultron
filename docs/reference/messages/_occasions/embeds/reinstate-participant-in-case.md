<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Reinstate participant in case"

    The Case Owner's own reinstatement of the removed actor named by the object. The CASE_MANAGER records it as the ledger entry and announces it to the actor, which becomes active again and receives the ledger entries it missed.

    - **When…** the Case Owner reinstates a removed Participant
    - **Send:** `Add(Actor)[target=VulnerabilityCase]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the Case Owner
    - **Reference:** [Reinstate participant in case](../../case_management.md#reinstate-participant-in-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("reinstate_participant_in_case"))
        ```
