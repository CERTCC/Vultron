<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Close report"

    Closes the report, moving the sender's RM state to Closed.

    - **When…** a report receiver closes the report
    - **Send:** `Reject(Offer(VulnerabilityReport))`
    - **Sent by:** an active participant (usually: vendor, coordinator)
    - **Reference:** [Close report](../../rm.md#report-closed)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            close_report,
            json2md,
        )

        print(json2md(close_report()))
        ```
