<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Update Case Owner { #update-case-owner }

Carries the case with its new owner in attributedTo. The CASE_MANAGER commits it after the Accept of the transfer and after each participant record whose CASE_OWNER role moved.

=== "Details"

    - **When…** the CASE_MANAGER records the new Case Owner once a case ownership transfer is accepted
    - **Send:** `Update(VulnerabilityCase)`
    - **Send to:** a participant
    - **Sent by:** internal to the CASE_MANAGER
    - **Mapping status:** [none](../../index.md#mapping-status)

    Each participant learns of it from the case ledger, so it is addressed to nobody.

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        update_case,
        json2md,
    )

    print(json2md(update_case()))
    ```
