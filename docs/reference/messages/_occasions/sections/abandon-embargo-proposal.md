<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Abandon embargo proposal { #abandon-embargo-proposal }

Cancels the proposal for the case. The CASE_MANAGER then withdraws each Invite it relayed for the proposal. This Reject is not the CASE_MANAGER's consent.

=== "Details"

    - **When…** the CASE_MANAGER abandons an open embargo proposal it received once the case is public, an exploit is public or attacks are observed
    - **Send:** `Reject(Invite(EmbargoEvent)[context=VulnerabilityCase])`
    - **Send to:** a participant
    - **Sent by:** the CASE_MANAGER
    - **Formal definition:** [Embargo Proposal Rejection (ER)](../../../formal_protocol/messages.md#em-message-types)
    - **Mapping status:** [expansion](../../index.md#mapping-status)

    Each participant learns of it from the case ledger, so it is addressed to nobody.

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        abandon_embargo_proposal,
        json2md,
    )

    print(json2md(abandon_embargo_proposal()))
    ```
