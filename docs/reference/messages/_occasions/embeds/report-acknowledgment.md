<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Report Acknowledgment (RK)"

    Acknowledges receipt of the submitted report. Report submission is not replicated through the case ledger, so the acknowledgment is an explicit message.

    - **When…** a report receiver has received a submitted report
    - **Send:** `Read(Offer(VulnerabilityReport))`
    - **Send to:** an actor outside any case
    - **Sent by:** the addressee of the vulnerability report offer (usually: vendor, coordinator)
    - **Reference:** [Report Acknowledgment (RK)](../../rm.md#report-acknowledgment)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            read_report,
            json2md,
        )

        print(json2md(read_report()))
        ```
