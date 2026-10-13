<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Embargo Revision Rejection (EJ)"

    Records the sender's own refusal of the revision. The Case Owner keeps the prior terms by sending its decision.

    - **When…** a Participant refuses a proposed embargo revision
    - **Send:** `Reject(Invite(Event)[context=VulnerabilityCase])`
    - **Sent by:** the invitee
    - **Distinguished by:** EM state `REVISE`
    - **Reference:** [Embargo Revision Rejection (EJ)](../../em.md#embargo-revision-rejection)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            reject_embargo_revision,
            json2md,
        )

        print(json2md(reject_embargo_revision()))
        ```
