<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Propose case ownership transfer"

    Asks the CASE_MANAGER to offer the case to another participant, for example from a Reporter to a Coordinator. The CASE_MANAGER offers the case only to an active participant, so the Case Owner invites any other actor first. The inner Offer names the case, the new owner as its target and, optionally, an `endTime` after which the CASE_MANAGER refuses an answer: the offer is then closed, with nothing recorded or sent. The CASE_MANAGER makes the offer itself.

    - **When…** the Case Owner proposes to transfer ownership of the case to another participant
    - **Send:** `Offer(Offer(VulnerabilityCase))`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the Case Owner
    - **Reference:** [Propose case ownership transfer](../../case_management.md#propose-case-ownership-transfer)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("propose_case_ownership_transfer"))
        ```
