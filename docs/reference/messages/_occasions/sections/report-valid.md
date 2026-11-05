<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Validate report { #report-valid }

Designates the report as valid, moving the sender's RM state to Valid.

=== "Details"

    - **When…** a report receiver judges the report valid
    - **Send:** `Accept(Offer(VulnerabilityReport))`
    - **Send to:** the case manager
    - **Sent by:** a participant (usually: vendor, coordinator)
    - **Seen in:** [How to Report a Vulnerability](../../../../howto/activitypub/activities/report_vulnerability.md)
    - **Formal definition:** [Report Valid (RV)](../../../formal_protocol/messages.md#rm-message-types)
    - **Mapping status:** [expansion](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        validate_report,
        json2md,
    )

    print(json2md(validate_report()))
    ```
