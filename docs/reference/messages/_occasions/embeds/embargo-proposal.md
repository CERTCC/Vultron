<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Embargo Proposal (EP)"

    Proposes embargo terms, such as an end date and time.

    - **When…** a Participant proposes embargo terms for a case with no active embargo
    - **Send:** `Invite(EmbargoEvent)[context=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case manager or an active participant
    - **Distinguished by:** EM state `NONE` or `PROPOSED`
    - **Reference:** [Embargo Proposal (EP)](../../em.md#embargo-proposal)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            propose_embargo,
            json2md,
        )

        print(json2md(propose_embargo()))
        ```
