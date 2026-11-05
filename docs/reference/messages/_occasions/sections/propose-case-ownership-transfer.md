<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Propose case ownership transfer { #propose-case-ownership-transfer }

Asks the Case Manager to offer the case to another participant, for example from a Reporter to a Coordinator. The Case Manager offers the case only to an active participant, so the Case Owner invites any other actor first. The inner Offer names the case, the new owner as its target and, optionally, an `endTime` after which the Case Manager refuses an answer: the offer is then closed, with nothing recorded or sent. The Case Manager makes the offer itself.

=== "Details"

    - **When…** the Case Owner proposes to transfer ownership of the case to another participant
    - **Send:** `Offer(Offer(VulnerabilityCase))`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Mapping status:** [none](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        propose_case_ownership_transfer,
        json2md,
    )

    print(json2md(propose_case_ownership_transfer()))
    ```
