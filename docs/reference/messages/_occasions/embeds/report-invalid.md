<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Invalidate report"

    Designates the report as invalid, moving the sender's RM state to Invalid.

    - **When…** a report receiver judges the report invalid
    - **Send:** `TentativeReject(Offer(VulnerabilityReport))`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** a participant (usually: vendor, coordinator)
    - **Reference:** [Invalidate report](../../rm.md#report-invalid)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("invalidate_report"))
        ```
