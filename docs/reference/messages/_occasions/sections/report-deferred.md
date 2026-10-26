<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Report/Case Deferred (RD) { #report-deferred }

Ignores the case, moving the sender's RM state to Deferred. Deferring is a case-participation decision, so the verb names the case rather than the report.

=== "Details"

    - **When…** a Participant defers further action on the case
    - **Send:** `Ignore(VulnerabilityCase)`
    - **Send to:** the case manager
    - **Sent by:** a participant
    - **Seen in:** [How to Advance a Case Through Report Management](../../../../howto/activitypub/activities/manage_case.md)
    - **Formal definition:** [Report/Case Deferred (RD)](../../../formal_protocol/messages.md#rm-message-types)
    - **Mapping status:** [direct](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        defer_case,
        json2md,
    )

    print(json2md(defer_case()))
    ```
