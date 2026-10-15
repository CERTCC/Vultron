<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Embargo Revision Proposal (EV)"

    Proposes a revision to the terms of the active embargo. The wire form is the same as a first proposal; the receiver's EM state makes it a revision.

    - **When…** a Participant proposes revised terms for the active embargo
    - **Send:** `Invite(Event)[context=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case manager or an active participant
    - **Distinguished by:** EM state `ACTIVE` or `REVISE`
    - **Reference:** [Embargo Revision Proposal (EV)](../../em.md#embargo-revision-proposal)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            propose_embargo_revision,
            json2md,
        )

        print(json2md(propose_embargo_revision()))
        ```
