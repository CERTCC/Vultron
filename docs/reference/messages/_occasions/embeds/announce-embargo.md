<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Announce embargo"

    Tells participants the terms of the active embargo. It proposes nothing.

    - **When…** the Case Manager states the terms of the embargo in force
    - **Send:** `Announce(Event)[context=VulnerabilityCase]`
    - **Sent by:** the case manager
    - **Reference:** [Announce embargo](../../em.md#announce-embargo)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            announce_embargo,
            json2md,
        )

        print(json2md(announce_embargo()))
        ```
