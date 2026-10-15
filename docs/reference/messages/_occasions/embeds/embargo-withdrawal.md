<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Withdraw from embargo"

    Ends the sender's own consent to the embargo in force, and to any revision it had agreed to. The embargo stays in force for every other participant.

    - **When…** a Participant bound by the active embargo stops complying with it
    - **Send:** `Leave(Event)[context=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** a participant
    - **Reference:** [Withdraw from embargo](../../em.md#embargo-withdrawal)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            withdraw_from_embargo,
            json2md,
        )

        print(json2md(withdraw_from_embargo()))
        ```
