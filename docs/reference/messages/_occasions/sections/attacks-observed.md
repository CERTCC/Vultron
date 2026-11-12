<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Attacks observed in a case status { #attacks-observed }

Tells a participant that the case status now records that attackers are exploiting the vulnerability.

=== "Details"

    - **When…** the CASE_MANAGER records that attackers are exploiting the vulnerability
    - **Send:** `Add(CaseStatus)[target=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** the CASE_MANAGER
    - **Distinguished by:** `pxaState` = `pxA`
    - **Formal definition:** [Attacks Observed (CA)](../../../formal_protocol/messages.md#cs-message-types)
    - **Mapping status:** [collapse](../../index.md#mapping-status)

    Only the CASE_MANAGER sends a case status, as its record of the `pxaState` it adopted, and a receiver refuses one from any other sender. A participant reports public awareness, a public exploit or observed attacks in its own participant status instead.

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("add_attacks_observed_to_case"))
    ```
