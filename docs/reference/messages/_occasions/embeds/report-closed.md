<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Close report"

    Closes the report, moving the sender's RM state to Closed. Once a case holds the report, its Case Owner closes the case with Leave(VulnerabilityCase) instead, and every receiver refuses a Close(Report) for it.

    - **When…** a report receiver closes a report no case holds
    - **Send:** `Reject(Offer(VulnerabilityReport))`
    - **Send to:** an actor outside any case
    - **Sent by:** the addressee of the vulnerability report offer (usually: vendor, coordinator)
    - **Reference:** [Close report](../../rm.md#report-closed)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            close_report,
            json2md,
        )

        print(json2md(close_report()))
        ```
