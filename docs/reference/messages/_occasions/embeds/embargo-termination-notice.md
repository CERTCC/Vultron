<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Tell a participant the embargo has ended"

    Tells one participant that the embargo has ended, with immediate effect. The CASE_MANAGER sends one to each participant other than itself, naming the Case Owner in `attributedTo` when the Case Owner asked for the termination.

    - **When…** the CASE_MANAGER ends the active embargo, on its own decision or on the Case Owner's
    - **Send:** `Remove(EmbargoEvent)`
    - **Send to:** a participant
    - **Sent by:** the CASE_MANAGER
    - **Reference:** [Tell a participant the embargo has ended](../../em.md#embargo-termination-notice)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("notify_embargo_termination"))
        ```
