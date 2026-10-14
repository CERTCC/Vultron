<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Embargo Proposal Acceptance (EA)"

    Records the sender's own consent to the proposed terms. The embargo becomes active only when the Case Owner sends its decision.

    - **When…** a Participant agrees to proposed embargo terms
    - **Send:** `Accept(Invite(Event)[context=VulnerabilityCase])`
    - **Sent by:** the invitee
    - **Distinguished by:** EM state `PROPOSED`
    - **Reference:** [Embargo Proposal Acceptance (EA)](../../em.md#embargo-proposal-acceptance)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            accept_embargo,
            json2md,
        )

        print(json2md(accept_embargo()))
        ```
