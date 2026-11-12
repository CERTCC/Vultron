<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Add case reference to case { #add-case-reference-to-case }

Carries the reference in full, with the case as its target. At a case's creation it follows the genesis entry.

=== "Details"

    - **When…** the CASE_MANAGER brings a case reference into a case, such as one a new case takes from its CSAF report
    - **Send:** `Add(CaseReference)[target=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** internal to the CASE_MANAGER
    - **Mapping status:** [none](../../index.md#mapping-status)

    Each participant learns of it from the case ledger, so it is addressed to nobody.

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        add_case_reference_to_case,
        json2md,
    )

    print(json2md(add_case_reference_to_case()))
    ```
