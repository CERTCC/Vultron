<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Tell a participant the embargo has ended"

    Tells one participant that the embargo has ended, with immediate effect. The Case Manager sends one to each participant other than itself, naming the Case Owner in `attributedTo` when the Case Owner asked for the termination.

    - **When…** the Case Manager ends the active embargo, on its own decision or on the Case Owner's
    - **Send:** `Remove(Event)`
    - **Send to:** a participant
    - **Sent by:** the case manager
    - **Reference:** [Tell a participant the embargo has ended](../../em.md#embargo-termination-notice)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            notify_embargo_termination,
            json2md,
        )

        print(json2md(notify_embargo_termination()))
        ```
