<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Attacks observed in a case status"

    Tells a participant that the case status now records that attackers are exploiting the vulnerability.

    - **When…** the CASE_MANAGER records that attackers are exploiting the vulnerability
    - **Send:** `Add(CaseStatus)[target=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** the CASE_MANAGER
    - **Distinguished by:** `pxaState` = `pxA`
    - **Reference:** [Attacks observed in a case status](../../cs.md#attacks-observed)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("add_attacks_observed_to_case"))
        ```
