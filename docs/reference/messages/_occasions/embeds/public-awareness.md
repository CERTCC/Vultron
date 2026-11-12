<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Public awareness in a case status"

    Tells a participant that the case status now records that the public knows of the vulnerability.

    - **When…** the CASE_MANAGER records that the public knows of the vulnerability
    - **Send:** `Add(CaseStatus)[target=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** the CASE_MANAGER
    - **Distinguished by:** `pxaState` = `Pxa`
    - **Reference:** [Public awareness in a case status](../../cs.md#public-awareness)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("add_public_awareness_to_case"))
        ```
