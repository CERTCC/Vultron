<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Embargo Termination (ET)"

    Terminates the embargo with immediate effect.

    - **When…** the Case Owner terminates the active embargo
    - **Send:** `Remove(Event)`
    - **Send to:** the case manager
    - **Sent by:** the case manager or the case owner
    - **Reference:** [Embargo Termination (ET)](../../em.md#embargo-termination)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            remove_embargo,
            json2md,
        )

        print(json2md(remove_embargo()))
        ```
