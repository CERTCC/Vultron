<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Send Full-Case Invite"

    Sends the Full-Case Invite, which asks the Participant to judge the case. It carries the Case Manager's ledger position as the floor the reply must reach.

    - **When…** the Case Manager has replayed the case ledger to a newly joined Participant
    - **Send:** `Invite(Actor)[target=VulnerabilityCase]`
    - **Sent by:** the case manager
    - **Reference:** [Send Full-Case Invite](../../case_management.md#invite-actor-to-full-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            invite_to_full_case,
            json2md,
        )

        print(json2md(invite_to_full_case()))
        ```
