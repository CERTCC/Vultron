<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Withdraw an embargo invitation"

    Withdraws an Invite the Case Manager sent for the abandoned proposal. The Case Manager first rejects the proposal it received, which cancels it, then withdraws each Invite it relayed for it. When the Case Manager made the proposal itself, withdrawing that proposal is the cancel.

    - **When…** the Case Manager abandons an open embargo proposal once the case is public, an exploit is public or attacks are observed
    - **Send:** `Undo(Invite(Event)[context=VulnerabilityCase])`
    - **Send to:** a participant
    - **Sent by:** not handled
    - **Reference:** [Withdraw an embargo invitation](../../em.md#withdraw-embargo-invite)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            undo_embargo_invite,
            json2md,
        )

        print(json2md(undo_embargo_invite()))
        ```
