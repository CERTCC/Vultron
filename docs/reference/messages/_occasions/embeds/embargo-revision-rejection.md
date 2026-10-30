<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Embargo Revision Rejection (EJ)"

    Rejects the revision for the case. The active embargo stays in force on its prior terms.

    - **When…** the Case Owner decides to reject a proposed revision
    - **Send:** `Reject(EmbargoEvent)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Distinguished by:** EM state `REVISE`
    - **Reference:** [Embargo Revision Rejection (EJ)](../../em.md#embargo-revision-rejection)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            reject_embargo_revision_proposal,
            json2md,
        )

        print(json2md(reject_embargo_revision_proposal()))
        ```
