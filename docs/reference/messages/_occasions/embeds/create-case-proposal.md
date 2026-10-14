<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Create case proposal"

    Submits a case proposal for the attached report to the service's inbox. No case exists yet.

    - **When…** a report receiver asks a Case Actor Service to open a case for a report
    - **Send:** `Create(CaseProposal)`
    - **Sent by:** not yet checked (usually: vendor, coordinator)
    - **Reference:** [Create case proposal](../../case_proposal.md#create-case-proposal)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            create_case_proposal,
            json2md,
        )

        print(json2md(create_case_proposal()))
        ```
