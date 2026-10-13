<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Report/Case Deferred (RD)"

    Ignores the case, moving the sender's RM state to Deferred. Deferring is a case-participation decision, so the verb names the case rather than the report.

    - **When…** a Participant defers further action on the case
    - **Send:** `Ignore(VulnerabilityCase)`
    - **Sent by:** an active participant
    - **Reference:** [Report/Case Deferred (RD)](../../rm.md#report-deferred)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            defer_case,
            json2md,
        )

        print(json2md(defer_case()))
        ```
