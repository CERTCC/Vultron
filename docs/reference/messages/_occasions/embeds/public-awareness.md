<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Public Awareness (CP)"

    Announces evidence that the vulnerability is known to the public.

    - **When…** a Participant learns that the public knows of the vulnerability
    - **Send:** `Add(CaseStatus)[target=VulnerabilityCase]`
    - **Sent by:** not yet checked
    - **Distinguished by:** `pxa_state` = `Pxa`
    - **Reference:** [Public Awareness (CP)](../../cs.md#public-awareness)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            add_public_awareness_to_case,
            json2md,
        )

        print(json2md(add_public_awareness_to_case()))
        ```
