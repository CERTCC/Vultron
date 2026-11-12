<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Send Full-Case Invite"

    Sends the Full-Case Invite, which asks the Participant to judge the case. It carries the CASE_MANAGER's ledger position as the floor the reply must reach.

    - **When…** the CASE_MANAGER has replayed the case ledger to a newly joined Participant
    - **Send:** `Invite(Actor)[target=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** the CASE_MANAGER
    - **Reference:** [Send Full-Case Invite](../../case_management.md#invite-actor-to-full-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("invite_to_full_case"))
        ```
