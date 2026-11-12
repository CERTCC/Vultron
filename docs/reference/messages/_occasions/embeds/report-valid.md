<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Validate report"

    Designates the report as valid, moving the sender's RM state to Valid.

    - **When…** a report receiver judges the report valid
    - **Send:** `Accept(Offer(VulnerabilityReport))`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** a participant (usually: vendor, coordinator)
    - **Reference:** [Validate report](../../rm.md#report-valid)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("validate_report"))
        ```
