<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Agree to an embargo revision"

    Records the sender's own consent to the revision. The revision replaces the active embargo only when the Case Owner sends its decision.

    - **When…** a Participant agrees to a proposed embargo revision
    - **Send:** `Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])`
    - **Send to:** the case manager
    - **Sent by:** the invitee
    - **Distinguished by:** EM state `REVISE`
    - **Reference:** [Agree to an embargo revision](../../em.md#agree-to-embargo-revision)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            accept_embargo_revision,
            json2md,
        )

        print(json2md(accept_embargo_revision()))
        ```
