<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Validate report { #report-valid }

Designates the report as valid, moving the sender's RM state to Valid.

=== "Details"

    - **When…** a report receiver judges the report valid
    - **Send:** `Accept(Offer(VulnerabilityReport))`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** a participant (usually: vendor, coordinator)
    - **Seen in:** [How to Report a Vulnerability](../../../../howto/activitypub/activities/report_vulnerability.md)
    - **Formal definition:** [Report Valid (RV)](../../../formal_protocol/messages.md#rm-message-types)
    - **Mapping status:** [expansion](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("validate_report"))
    ```
