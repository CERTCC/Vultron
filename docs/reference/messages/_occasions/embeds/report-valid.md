<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Validate report"

    Designates the report as valid, moving the sender's RM state to Valid.

    - **When…** a report receiver judges the report valid
    - **Send:** `Accept(Offer(VulnerabilityReport))`
    - **Send to:** the case manager
    - **Sent by:** a participant (usually: vendor, coordinator)
    - **Reference:** [Validate report](../../rm.md#report-valid)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            validate_report,
            json2md,
        )

        print(json2md(validate_report()))
        ```
