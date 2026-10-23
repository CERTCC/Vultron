<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Reject Full-Case Invite"

    Rejects the Full-Case Invite, which records RM Closed. It carries the sender's own ledger position.

    - **When…** a Participant asked by a Full-Case Invite closes the case
    - **Send:** `Reject(Invite(Actor)[target=VulnerabilityCase])`
    - **Send to:** the case manager
    - **Sent by:** the invitee
    - **Reference:** [Reject Full-Case Invite](../../case_management.md#reject-full-case-invite)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            reject_full_case_invite,
            json2md,
        )

        print(json2md(reject_full_case_invite()))
        ```
