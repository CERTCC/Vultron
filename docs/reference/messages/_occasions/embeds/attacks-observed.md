<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Attacks Observed (CA)"

    Announces evidence that attackers are exploiting the vulnerability.

    - **When…** a Participant observes attacks that exploit the vulnerability
    - **Send:** `Add(CaseStatus)[target=VulnerabilityCase]`
    - **Sent by:** not yet checked
    - **Distinguished by:** `pxa_state` = `pxA`
    - **Reference:** [Attacks Observed (CA)](../../cs.md#attacks-observed)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            add_attacks_observed_to_case,
            json2md,
        )

        print(json2md(add_attacks_observed_to_case()))
        ```
