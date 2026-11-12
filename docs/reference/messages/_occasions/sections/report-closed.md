<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Close report { #report-closed }

Closes the report, moving the sender's RM state to Closed. Once a case holds the report, its Case Owner closes the case with Leave(VulnerabilityCase) instead, and every receiver refuses a Reject(Offer(VulnerabilityReport)) for it.

=== "Details"

    - **When…** a report receiver closes a report no case holds
    - **Send:** `Reject(Offer(VulnerabilityReport))`
    - **Send to:** an actor outside any case
    - **Sent by:** the addressee of the vulnerability report offer (usually: vendor, coordinator)
    - **Seen in:** [How to Advance a Case Through Report Management](../../../../howto/activitypub/activities/manage_case.md), [How to Report a Vulnerability](../../../../howto/activitypub/activities/report_vulnerability.md)
    - **Formal definition:** [Report Closed (RC)](../../../formal_protocol/messages.md#rm-message-types)
    - **Mapping status:** [expansion](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("close_report"))
    ```
