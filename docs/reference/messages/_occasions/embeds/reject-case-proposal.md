<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Reject case proposal"

    Rejects the case proposal. No case is opened.

    - **When…** a Case Actor Service declines to open the proposed case
    - **Send:** `Reject(CaseProposal)`
    - **Sent by:** the addressee of the case proposal
    - **Reference:** [Reject case proposal](../../case_proposal.md#reject-case-proposal)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            reject_case_proposal,
            json2md,
        )

        print(json2md(reject_case_proposal()))
        ```
