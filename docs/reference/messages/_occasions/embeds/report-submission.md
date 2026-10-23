<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Report Submission (RS)"

    Offers the report to a new Participant. The Offer may carry proposed embargo terms.

    - **When…** a Reporter submits a vulnerability report to a Vendor or Coordinator
    - **Send:** `Offer(VulnerabilityReport)`
    - **Send to:** an actor outside any case
    - **Sent by:** any actor (usually: reporter)
    - **Reference:** [Report Submission (RS)](../../rm.md#report-submission)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            submit_report,
            json2md,
        )

        print(json2md(submit_report()))
        ```
