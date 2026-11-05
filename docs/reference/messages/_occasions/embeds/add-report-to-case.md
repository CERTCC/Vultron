<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Add report to case"

    Adds a vulnerability report to the case named by the target.

    - **When…** the Case Owner links a further report to an existing case
    - **Send:** `Add(VulnerabilityReport)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Reference:** [Add report to case](../../case_management.md#add-report-to-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            add_report_to_case,
            json2md,
        )

        print(json2md(add_report_to_case()))
        ```
