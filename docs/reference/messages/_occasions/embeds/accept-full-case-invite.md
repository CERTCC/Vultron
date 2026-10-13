<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Accept Full-Case Invite"

    Accepts the Full-Case Invite, which records RM Valid. It carries the sender's own ledger position.

    - **When…** a Participant asked by a Full-Case Invite judges the case valid
    - **Send:** `Accept(Invite(Actor)[target=VulnerabilityCase])`
    - **Sent by:** the invitee
    - **Reference:** [Accept Full-Case Invite](../../case_management.md#accept-full-case-invite)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            accept_full_case_invite,
            json2md,
        )

        print(json2md(accept_full_case_invite()))
        ```
