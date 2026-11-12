<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Add case reference to case"

    Carries the reference in full, with the case as its target. At a case's creation it follows the genesis entry.

    - **When…** the CASE_MANAGER brings a case reference into a case, such as one a new case takes from its CSAF report
    - **Send:** `Add(CaseReference)[target=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** internal to the CASE_MANAGER
    - **Reference:** [Add case reference to case](../../case_management.md#add-case-reference-to-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("add_case_reference_to_case"))
        ```
