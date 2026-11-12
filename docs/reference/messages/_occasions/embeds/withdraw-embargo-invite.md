<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Withdraw an embargo invitation"

    Withdraws an Invite the CASE_MANAGER sent for the abandoned proposal. The CASE_MANAGER first rejects the proposal it received, which cancels it, then withdraws each Invite it relayed for it. When the CASE_MANAGER made the proposal itself, withdrawing that proposal is the cancel.

    - **When…** the CASE_MANAGER abandons an open embargo proposal once the case is public, an exploit is public or attacks are observed
    - **Send:** `Undo(Invite(EmbargoEvent)[context=VulnerabilityCase])`
    - **Send to:** a participant
    - **Sent by:** internal to the CASE_MANAGER
    - **Reference:** [Withdraw an embargo invitation](../../em.md#withdraw-embargo-invite)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("undo_embargo_invite"))
        ```
