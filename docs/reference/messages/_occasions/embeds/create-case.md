<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Create case"

    Mints the vulnerability case, seats its initial participants and links the report.

    - **When…** the Case Manager has opened a case for a submitted report
    - **Send:** `Create(VulnerabilityCase)`
    - **Send to:** a participant
    - **Sent by:** the addressee of the case proposal
    - **Reference:** [Create case](../../case_management.md#create-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            create_case,
            json2md,
        )

        print(json2md(create_case()))
        ```
