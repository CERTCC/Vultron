<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Case Owner offers case ownership"

    The Case Owner's own Offer, sent to the CASE_MANAGER only: the case as the object and the new owner as the target, for example from a Reporter to a Coordinator. The CASE_MANAGER offers the case only to an active participant, so the Case Owner invites any other actor first. An optional `endTime` is the deadline to answer: after it the CASE_MANAGER refuses an answer, and the offer is closed with nothing recorded or sent. The CASE_MANAGER records this Offer and makes its own Offer to the new owner, which answers that one.

    - **When…** the Case Owner offers ownership of the case to another participant
    - **Send:** `Offer(VulnerabilityCase)`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the Case Owner
    - **Reference:** [Case Owner offers case ownership](../../case_management.md#propose-case-ownership-transfer)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("propose_case_ownership_transfer"))
        ```
